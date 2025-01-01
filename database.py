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

        cursor.execute('SELECT id FROM sites WHERE name = ? AND uri_check = ?', (site['title'], site['uri']))
        wm_data_id = cursor.fetchone()

        if username_id and wm_data_id:
            cursor.execute('''
                INSERT INTO username_correlations (username_id, site_id)
                VALUES (?, ?)
            ''', (username_id[0], wm_data_id[0]))
            conn.commit()
            logger.info(f"Correlation for username '{username}' and site '{site['uri']}' inserted.")
        else:
            logger.warning(f"No correlation found for username '{username}' and site '{site[uri]}'.")
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
        cursor.execute('SELECT name, uri_check, cat FROM sites')
        def serialize_site(site: list) -> dict:
            return {
                "title": site[0],
                "uri": site[1],
                "category": site[2],
            }
        sites = cursor.fetchall()
        return [serialize_site(site) for site in sites]
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in get_all_sites: {e}")
        raise e


def get_sites_by_username(username):
    try:
        query = """
            SELECT s.name, s.uri_check, s.cat, u.search_timestamp, uc.found_timestamp
            FROM sites s
            JOIN username_correlations uc ON s.id = uc.site_id
            JOIN usernames_searched u ON u.id = uc.username_id
            WHERE u.username = ?;
        """
        cursor = conn.cursor()
        cursor.execute(query, (username,))
        sites = cursor.fetchall()

        def serialize_site(site: list) -> dict:
            return {
                "title": site[0],
                "uri": site[1].format(account=username),
                "category": site[2],
                "search_timestamp": site[3],
                "found_timestamp": site[4]
            }

        return [serialize_site(site) for site in sites]
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in get_sites_by_username: {e}")
        raise e
        
def delete_search_history(username: str):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM usernames_searched WHERE username = ?;
        ''', (username,))
        user_id = cursor.fetchone() 
        if user_id:
            user_id = user_id[0]  # Extract the ID from the result tuple.
            cursor.execute('''
                DELETE FROM username_correlations WHERE username_id = ?;
            ''', (user_id,))
        cursor.execute('''
            DELETE FROM usernames_searched WHERE id = ?;
        ''', (user_id,))
        conn.commit()
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error in delete_search_history: {e}")
        raise e