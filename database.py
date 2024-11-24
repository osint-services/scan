import sqlite3
import logging

# Connect to the SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('whatsmyname.db')

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # You can change to DEBUG or ERROR based on your needs

def has_username_been_searched(username):
    try:
        cursor = conn.cursor()
        query = """
            SELECT 1
            FROM usernames_searched
            WHERE username = ?;
        """
        cursor.execute(query, (username,))
        result = cursor.fetchone()
        if result:
            logger.info(f"Username '{username}' has been searched.")
            return True
        else:
            logger.info(f"Username '{username}' has not been searched.")
            return False
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in has_username_been_searched: {e}")
        raise e


def insert_username(username):
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO usernames_searched (username)
            VALUES (?);
        """
        cursor.execute(query, (username,))
        conn.commit()
        logger.info(f"Username '{username}' has been inserted.")
    except sqlite3.IntegrityError:
        logger.warning(f"Username '{username}' already exists.")
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in insert_username: {e}")
        raise e


def insert_username_correlation(username, site):
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM usernames_searched WHERE username = ?', (username,))
        username_id = cursor.fetchone()

        cursor.execute('SELECT id FROM sites WHERE name = ? AND uri_check = ?', (site[1], site[2]))
        wm_data_id = cursor.fetchone()

        if username_id and wm_data_id:
            cursor.execute('''
                INSERT INTO username_correlations (username_id, site_id)
                VALUES (?, ?)
            ''', (username_id[0], wm_data_id[0]))
            conn.commit()
            logger.info(f"Correlation for username '{username}' and site '{site[1]}' inserted.")
        else:
            logger.warning(f"No correlation found for username '{username}' and site '{site[1]}'.")
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in insert_username_correlation: {e}")
        raise e


def insert_sites(sites: list[dict]):
    try:
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT INTO sites (name, uri_check, cat)
            VALUES (:name, :uri_check, :cat);
        ''', sites)
        conn.commit()
        logger.info(f"Inserted {len(sites)} sites into the database.")
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in insert_sites: {e}")
        raise e


def get_all_sites():
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sites')
        return cursor.fetchall()
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in get_all_sites: {e}")
        raise e


def get_sites_by_username(username):
    try:
        query = """
            SELECT s.name, s.uri_check, s.cat
            FROM sites s
            JOIN username_correlations uc ON s.id = uc.site_id
            JOIN usernames_searched u ON u.id = uc.username_id
            WHERE u.username = ?;
        """
        cursor = conn.cursor()
        cursor.execute(query, (username,))
        sites = cursor.fetchall()

        return [{"name": site[0], "uri_check": site[1].format(account=username), "cat": site[2]} for site in sites]
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in get_sites_by_username: {e}")
        raise e