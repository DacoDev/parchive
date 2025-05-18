import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from ..models.models import Show, Episode

class DatabaseService:
    def __init__(self, db_path: str = "data/urls.db"):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Create the shows table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    description TEXT,
                    author TEXT,
                    image_url TEXT,
                    category TEXT,
                    language TEXT,
                    copyright TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create the episodes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    episode_number TEXT NOT NULL,
                    itunes_episode TEXT,
                    description TEXT,
                    summary TEXT,
                    author TEXT,
                    image_url TEXT,
                    duration TEXT,
                    keywords TEXT,
                    published_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_hash TEXT,
                    image_file_hash TEXT,
                    is_downloaded BOOLEAN DEFAULT 0,
                    was_downloaded BOOLEAN DEFAULT 0,
                    download_date TIMESTAMP,
                    deleted_date TIMESTAMP,
                    FOREIGN KEY (show_id) REFERENCES shows (id) ON DELETE CASCADE
                )
            """)
            
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Run migrations to add new columns to existing tables if needed
            self._run_migrations(conn)

    def _run_migrations(self, conn: sqlite3.Connection):
        """Run database migrations to update schema"""
        # Check if file_hash column exists in episodes table
        cursor = conn.execute("PRAGMA table_info(episodes)")
        episodes_columns = [row[1] for row in cursor.fetchall()]
        
        # Check shows table columns
        cursor = conn.execute("PRAGMA table_info(shows)")
        shows_columns = [row[1] for row in cursor.fetchall()]
        
        # Add file_hash column if it doesn't exist
        if 'file_hash' not in episodes_columns:
            print("Migrating database: Adding file_hash column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN file_hash TEXT")
            conn.commit()
            
        # Add image_file_hash column if it doesn't exist
        if 'image_file_hash' not in episodes_columns:
            print("Migrating database: Adding image_file_hash column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN image_file_hash TEXT")
            conn.commit()
            
        # Add download tracking columns if they don't exist
        if 'is_downloaded' not in episodes_columns:
            print("Migrating database: Adding is_downloaded column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN is_downloaded BOOLEAN DEFAULT 0")
            conn.commit()
            
        if 'was_downloaded' not in episodes_columns:
            print("Migrating database: Adding was_downloaded column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN was_downloaded BOOLEAN DEFAULT 0")
            conn.commit()
            
        if 'download_date' not in episodes_columns:
            print("Migrating database: Adding download_date column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN download_date TIMESTAMP")
            conn.commit()
            
        if 'deleted_date' not in episodes_columns:
            print("Migrating database: Adding deleted_date column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN deleted_date TIMESTAMP")
            conn.commit()
            
        # Add new metadata columns to shows table
        if 'description' not in shows_columns:
            print("Migrating database: Adding description column to shows table")
            conn.execute("ALTER TABLE shows ADD COLUMN description TEXT")
            conn.commit()
            
        if 'author' not in shows_columns:
            print("Migrating database: Adding author column to shows table")
            conn.execute("ALTER TABLE shows ADD COLUMN author TEXT")
            conn.commit()
            
        if 'image_url' not in shows_columns:
            print("Migrating database: Adding image_url column to shows table")
            conn.execute("ALTER TABLE shows ADD COLUMN image_url TEXT")
            conn.commit()
            
        if 'category' not in shows_columns:
            print("Migrating database: Adding category column to shows table")
            conn.execute("ALTER TABLE shows ADD COLUMN category TEXT")
            conn.commit()
            
        if 'language' not in shows_columns:
            print("Migrating database: Adding language column to shows table")
            conn.execute("ALTER TABLE shows ADD COLUMN language TEXT")
            conn.commit()
            
        if 'copyright' not in shows_columns:
            print("Migrating database: Adding copyright column to shows table")
            conn.execute("ALTER TABLE shows ADD COLUMN copyright TEXT")
            conn.commit()
            
        # Add new metadata columns to episodes table
        if 'itunes_episode' not in episodes_columns:
            print("Migrating database: Adding itunes_episode column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN itunes_episode TEXT")
            conn.commit()
            
        if 'description' not in episodes_columns:
            print("Migrating database: Adding description column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN description TEXT")
            conn.commit()
            
        if 'summary' not in episodes_columns:
            print("Migrating database: Adding summary column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN summary TEXT")
            conn.commit()
            
        if 'author' not in episodes_columns:
            print("Migrating database: Adding author column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN author TEXT")
            conn.commit()
            
        if 'image_url' not in episodes_columns:
            print("Migrating database: Adding image_url column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN image_url TEXT")
            conn.commit()
            
        if 'duration' not in episodes_columns:
            print("Migrating database: Adding duration column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN duration TEXT")
            conn.commit()
            
        if 'keywords' not in episodes_columns:
            print("Migrating database: Adding keywords column to episodes table")
            conn.execute("ALTER TABLE episodes ADD COLUMN keywords TEXT")
            conn.commit()

    def _ensure_db(self):
        """Ensure database and tables exist before any operation"""
        # Check if database file exists
        if not os.path.exists(self.db_path):
            # Create database directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._init_db()
        else:
            # Connect to database and check if tables exist
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Try to count shows table rows as a test
                    cursor = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='shows'")
                    if cursor.fetchone()[0] == 0:
                        # Tables don't exist, initialize
                        self._init_db()
            except sqlite3.OperationalError:
                # Table doesn't exist, initialize database
                self._init_db()

    # New methods for shows
    def add_show(self, show: Show) -> int:
        """Add a new show to the database or return existing ID if URL already exists"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            # Check if a show with this URL already exists
            cursor = conn.execute("SELECT id FROM shows WHERE url = ?", (show.url,))
            existing = cursor.fetchone()
            
            if existing:
                # If show already exists, return its ID
                return existing[0]
                
            # Otherwise, insert new show
            cursor = conn.execute(
                """
                INSERT INTO shows 
                (name, url, description, author, image_url, category, language, copyright) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    show.name, 
                    show.url, 
                    show.description, 
                    show.author, 
                    show.image_url, 
                    show.category, 
                    show.language, 
                    show.copyright
                )
            )
            return cursor.lastrowid

    def get_show(self, show_id: int) -> Optional[Show]:
        """Get a show by ID"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM shows WHERE id = ?", (show_id,))
            row = cursor.fetchone()
            if row:
                return Show(
                    id=row[0],
                    name=row[1],
                    url=row[2],
                    description=row[3] if len(row) > 3 else "",
                    author=row[4] if len(row) > 4 else "",
                    image_url=row[5] if len(row) > 5 else "",
                    category=row[6] if len(row) > 6 else "",
                    language=row[7] if len(row) > 7 else "",
                    copyright=row[8] if len(row) > 8 else "",
                    created_at=datetime.fromisoformat(row[9]) if len(row) > 9 and row[9] else None,
                    updated_at=datetime.fromisoformat(row[10]) if len(row) > 10 and row[10] else None
                )
            return None

    def get_show_by_url(self, url: str) -> Optional[Show]:
        """Get a show by its feed URL"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM shows WHERE url = ?", (url,))
            row = cursor.fetchone()
            if row:
                return Show(
                    id=row[0],
                    name=row[1],
                    url=row[2],
                    description=row[3] if len(row) > 3 else "",
                    author=row[4] if len(row) > 4 else "",
                    image_url=row[5] if len(row) > 5 else "",
                    category=row[6] if len(row) > 6 else "",
                    language=row[7] if len(row) > 7 else "",
                    copyright=row[8] if len(row) > 8 else "",
                    created_at=datetime.fromisoformat(row[9]) if len(row) > 9 and row[9] else None,
                    updated_at=datetime.fromisoformat(row[10]) if len(row) > 10 and row[10] else None
                )
            return None

    def list_shows(self) -> List[Show]:
        """List all shows"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM shows ORDER BY name")
            return [
                Show(
                    id=row[0],
                    name=row[1],
                    url=row[2],
                    description=row[3] if len(row) > 3 else "",
                    author=row[4] if len(row) > 4 else "",
                    image_url=row[5] if len(row) > 5 else "",
                    category=row[6] if len(row) > 6 else "",
                    language=row[7] if len(row) > 7 else "",
                    copyright=row[8] if len(row) > 8 else "",
                    created_at=datetime.fromisoformat(row[9]) if len(row) > 9 and row[9] else None,
                    updated_at=datetime.fromisoformat(row[10]) if len(row) > 10 and row[10] else None
                )
                for row in cursor.fetchall()
            ]

    def update_show(self, show: Show) -> bool:
        """Update a show"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE shows 
                SET name = ?, url = ?, description = ?, author = ?, 
                    image_url = ?, category = ?, language = ?, copyright = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    show.name, 
                    show.url, 
                    show.description,
                    show.author,
                    show.image_url,
                    show.category,
                    show.language,
                    show.copyright,
                    show.id
                )
            )
            return cursor.rowcount > 0
            
    def delete_show(self, show_id: int) -> bool:
        """Delete a show and all its episodes"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            # Enable foreign keys to cascade delete
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.execute("DELETE FROM shows WHERE id = ?", (show_id,))
            return cursor.rowcount > 0
            
    # Methods for episodes
    def add_episode(self, episode: Episode) -> int:
        """Add a new episode to the database"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            # Check if episode already exists (by show_id and URL)
            cursor = conn.execute(
                "SELECT id FROM episodes WHERE show_id = ? AND url = ?", 
                (episode.show_id, episode.url)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Episode already exists, update its metadata and return its ID
                self.update_episode(episode)
                return existing[0]
                
            cursor = conn.execute(
                """
                INSERT INTO episodes 
                (show_id, title, url, episode_number, itunes_episode, description, summary,
                 author, image_url, duration, keywords, published_at, file_hash, image_file_hash,
                 is_downloaded, was_downloaded, download_date, deleted_date) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode.show_id, 
                    episode.title, 
                    episode.url, 
                    episode.episode_number,
                    episode.itunes_episode,
                    episode.description,
                    episode.summary,
                    episode.author,
                    episode.image_url,
                    episode.duration,
                    episode.keywords,
                    episode.published_at.isoformat() if episode.published_at else None,
                    episode.file_hash,
                    episode.image_file_hash,
                    1 if episode.is_downloaded else 0,
                    1 if episode.was_downloaded else 0,
                    episode.download_date.isoformat() if episode.download_date else None,
                    episode.deleted_date.isoformat() if episode.deleted_date else None
                )
            )
            return cursor.lastrowid
            
    def get_episode(self, episode_id: int) -> Optional[Episode]:
        """Get an episode by ID"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_episode(row)
            return None
            
    def _row_to_episode(self, row) -> Episode:
        """Convert a database row to an Episode object"""
        return Episode(
            id=row[0],
            show_id=row[1],
            title=row[2],
            url=row[3],
            episode_number=row[4],
            itunes_episode=row[5] if len(row) > 5 else "",
            description=row[6] if len(row) > 6 else "",
            summary=row[7] if len(row) > 7 else "",
            author=row[8] if len(row) > 8 else "",
            image_url=row[9] if len(row) > 9 else "",
            duration=row[10] if len(row) > 10 else "",
            keywords=row[11] if len(row) > 11 else "",
            published_at=datetime.fromisoformat(row[12]) if len(row) > 12 and row[12] else None,
            created_at=datetime.fromisoformat(row[13]) if len(row) > 13 and row[13] else None,
            updated_at=datetime.fromisoformat(row[14]) if len(row) > 14 and row[14] else None,
            file_hash=row[15] if len(row) > 15 else None,
            image_file_hash=row[16] if len(row) > 16 else None,
            is_downloaded=bool(row[17]) if len(row) > 17 else False,
            was_downloaded=bool(row[18]) if len(row) > 18 else False,
            download_date=datetime.fromisoformat(row[19]) if len(row) > 19 and row[19] else None,
            deleted_date=datetime.fromisoformat(row[20]) if len(row) > 20 and row[20] else None
        )
            
    def list_episodes(self, show_id: int, order_by: str = "published_at") -> List[Episode]:
        """List all episodes for a show
        
        Args:
            show_id: ID of the show
            order_by: Field to order by ('id', 'published_at', 'episode_number')
        """
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            # Determine the ORDER BY clause based on the parameter
            if order_by == "id":
                order_clause = "ORDER BY id ASC"
            elif order_by == "episode_number":
                order_clause = "ORDER BY episode_number ASC"
            else:  # Default to published_at
                order_clause = "ORDER BY published_at DESC, episode_number DESC"
                
            cursor = conn.execute(
                f"""
                SELECT * FROM episodes 
                WHERE show_id = ? 
                {order_clause}
                """, 
                (show_id,)
            )
            return [self._row_to_episode(row) for row in cursor.fetchall()]

    def update_episode(self, episode: Episode) -> bool:
        """Update an episode"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE episodes 
                SET title = ?, url = ?, episode_number = ?, itunes_episode = ?, 
                    description = ?, summary = ?, author = ?, image_url = ?, 
                    duration = ?, keywords = ?, published_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    episode.title, 
                    episode.url, 
                    episode.episode_number,
                    episode.itunes_episode,
                    episode.description,
                    episode.summary,
                    episode.author,
                    episode.image_url,
                    episode.duration,
                    episode.keywords,
                    episode.published_at.isoformat() if episode.published_at else None,
                    episode.id
                )
            )
            return cursor.rowcount > 0

    def delete_episode(self, episode_id: int) -> bool:
        """Delete an episode"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
            return cursor.rowcount > 0
            
    def delete_episodes_by_show(self, show_id: int) -> int:
        """Delete all episodes for a show, returns count of deleted episodes"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM episodes WHERE show_id = ?", (show_id,))
            return cursor.rowcount 

    def update_episode_file_hash(self, episode_id: int, file_hash: str) -> bool:
        """Update the file_hash for an episode"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE episodes 
                SET file_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (file_hash, episode_id)
            )
            return cursor.rowcount > 0

    def update_episode_image_file_hash(self, episode_id: int, image_file_hash: str) -> bool:
        """Update the image_file_hash for an episode"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE episodes 
                SET image_file_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (image_file_hash, episode_id)
            )
            return cursor.rowcount > 0

    def get_episode_by_file_hash(self, file_hash: str) -> Optional[Episode]:
        """Get an episode by its file hash"""
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM episodes WHERE file_hash = ?", (file_hash,))
            row = cursor.fetchone()
            if row:
                return self._row_to_episode(row)
            return None

    def update_episode_download_status(self, episode_id: int, is_downloaded: bool, file_hash: str = None) -> bool:
        """Update an episode's download status
        
        Args:
            episode_id: The ID of the episode
            is_downloaded: Whether the episode is currently downloaded
            file_hash: The hash of the downloaded file (if downloaded)
            
        Returns:
            bool: Whether the update was successful
        """
        self._ensure_db()
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.now().isoformat()
            
            if is_downloaded:
                # Mark as downloaded and update timestamp
                cursor = conn.execute(
                    """
                    UPDATE episodes 
                    SET is_downloaded = 1, 
                        was_downloaded = 1, 
                        download_date = ?, 
                        file_hash = ?,
                        deleted_date = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (now, file_hash, episode_id)
                )
            else:
                # Mark as deleted and update timestamp
                cursor = conn.execute(
                    """
                    UPDATE episodes 
                    SET is_downloaded = 0, 
                        deleted_date = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (now, episode_id)
                )
                
            return cursor.rowcount > 0 