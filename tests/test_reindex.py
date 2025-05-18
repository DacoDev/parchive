"""
Tests for the reindex functionality in the parchive application.
"""
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime
from app.services.database import DatabaseService
from app.models.models import Show, Episode

# Test data
TEST_SHOW = Show(
    id=999,
    name="Test Show",
    url="https://example.com/feed",
    created_at=datetime.now()
)

# Original episodes in the database
DB_EPISODES = [
    Episode(
        id=1,
        show_id=999,
        title="Episode 1",
        url="https://example.com/ep1",
        episode_number="1",
        published_at=datetime(2023, 1, 1),
        is_downloaded=True,
        download_date=datetime(2023, 1, 5)
    ),
    Episode(
        id=2,
        show_id=999,
        title="Episode 2",
        url="https://example.com/ep2",
        episode_number="2",
        published_at=datetime(2023, 1, 8)
    ),
    Episode(
        id=3,
        show_id=999,
        title="Episode 3",
        url="https://example.com/ep3",
        episode_number="3",
        published_at=datetime(2023, 1, 15)
    ),
    Episode(
        id=4,
        show_id=999,
        title="Episode to be removed",
        url="https://example.com/ep4-removed",
        episode_number="4",
        published_at=datetime(2023, 1, 22)
    )
]

# Feed episodes to compare against (with differences)
FEED_EPISODES = [
    {
        'title': "Episode 1",  # Unchanged
        'url': "https://example.com/ep1",
        'episode_number': "1",
        'published_at': datetime(2023, 1, 1)
    },
    {
        'title': "Episode 2 - Updated Title",  # Title modified
        'url': "https://example.com/ep2",
        'episode_number': "2",
        'published_at': datetime(2023, 1, 8)
    },
    {
        'title': "Episode 3",  # Episode number modified
        'url': "https://example.com/ep3",
        'episode_number': "3.5",
        'published_at': datetime(2023, 1, 15)
    },
    # Episode 4 missing (simulates removed from feed)
    {
        'title': "New Episode 5",  # New episode
        'url': "https://example.com/ep5-new",
        'episode_number': "5",
        'published_at': datetime(2023, 1, 29)
    }
]

# Mock feed data that would be returned by parse_rss_feed
MOCK_FEED_DATA = {
    'title': "Test Show",
    'url': "https://example.com/feed",
    'episodes': FEED_EPISODES
}


@pytest.fixture
def mock_db():
    """Create a mock database service"""
    with patch('app.services.database.DatabaseService') as mock:
        db_instance = MagicMock()
        
        # Mock the get_show method
        db_instance.get_show.return_value = TEST_SHOW
        
        # Mock the list_episodes method
        db_instance.list_episodes.return_value = DB_EPISODES
        
        # Mock update methods
        db_instance.update_episode.return_value = True
        db_instance.add_episode.return_value = 100  # Return a fake ID
        
        mock.return_value = db_instance
        yield db_instance


@pytest.fixture
def mock_xml_parser():
    """Mock the XML parser to return our test feed data"""
    with patch('app.utils.xml_parser.parse_rss_feed') as mock:
        mock.return_value = MOCK_FEED_DATA
        yield mock


@pytest.fixture
def mock_console():
    """Mock the Rich console to capture output"""
    with patch('app.main.console') as mock:
        yield mock


@patch('app.main.Confirm.ask')
def test_reindex_all_difference_types(mock_confirm, mock_db, mock_xml_parser, mock_console):
    """Test that reindex correctly identifies all three types of differences"""
    from app.main import reindex
    
    # Mock the confirmation to return True
    mock_confirm.return_value = True
    
    # Call the reindex function
    reindex(show_id=999, force=True)
    
    # Verify that the function identified all difference types
    # The differences should be reported through console.print
    
    # Check for modified episodes reporting
    modified_calls = [
        call for call in mock_console.print.call_args_list 
        if "[bold yellow]Modified episodes" in str(call)
    ]
    assert len(modified_calls) > 0, "Should report modified episodes"
    
    # Check for new episodes reporting
    new_episodes_calls = [
        call for call in mock_console.print.call_args_list 
        if "[bold green]New episodes" in str(call)
    ]
    assert len(new_episodes_calls) > 0, "Should report new episodes"
    
    # Check for missing episodes reporting
    missing_calls = [
        call for call in mock_console.print.call_args_list 
        if "[bold red]Episodes in database but missing from feed" in str(call)
    ]
    assert len(missing_calls) > 0, "Should report missing episodes"
    
    # Verify that the database was updated
    # 1. Update modified episodes
    assert mock_db.update_episode.called, "Should update modified episodes"
    
    # 2. Add new episodes
    assert mock_db.add_episode.called, "Should add new episodes"


@patch('app.main.Confirm.ask')
def test_reindex_no_differences(mock_confirm, mock_db, mock_console):
    """Test reindex when there are no differences"""
    from app.main import reindex
    
    # Mock feed data with no differences
    same_episodes = [
        {
            'title': episode.title,
            'url': episode.url,
            'episode_number': episode.episode_number,
            'published_at': episode.published_at
        }
        for episode in DB_EPISODES
    ]
    
    same_feed = {
        'title': TEST_SHOW.name,
        'url': TEST_SHOW.url,
        'episodes': same_episodes
    }
    
    # Mock the XML parser to return identical data
    with patch('app.utils.xml_parser.parse_rss_feed') as mock_xml:
        mock_xml.return_value = same_feed
        
        # Call the reindex function
        reindex(show_id=999, force=True)
        
        # Print mock call arguments for debugging
        print("Mock console calls:")
        for c in mock_console.print.call_args_list:
            print(f"  {c}")
            
        # Verify that no differences were reported by checking if any console message
        # contains some key phrases that would indicate no differences
        no_diff_calls = [
            call for call in mock_console.print.call_args_list 
            if any(msg in str(c) for msg in ["No differences", "no differences", "Successfully reindexed"])
        ]
        assert len(no_diff_calls) > 0, "Should report no differences"
        
        # Verify that the database was not updated
        mock_db.update_episode.assert_not_called()
        mock_db.add_episode.assert_not_called() 