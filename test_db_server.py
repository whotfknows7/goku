
import unittest
from unittest.mock import patch, MagicMock
from db_server import (
    update_user_xp,
    track_activity,
    check_boost_cooldown,
    update_boost_cooldown,
    check_activity_burst,
    delete_user_data
)

class TestActivityFunctions(unittest.TestCase):

    @patch('db_server.sqlite3.connect')
    def test_update_user_xp(self, mock_connect):
        # Mock the database connection and cursor
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        user_id = 12345
        xp_to_add = 50

        # Call the function
        update_user_xp(user_id, xp_to_add)

        # Assert that the database queries were called correctly
        mock_cursor.execute.assert_called_with(
            "INSERT INTO user_xp (user_id, xp) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET xp = xp + ?",
            (user_id, xp_to_add, xp_to_add)
        )
        mock_connect.return_value.commit.assert_called_once()

    @patch('db_server.sqlite3.connect')
    def test_track_activity(self, mock_connect):
        # Mock the database connection and cursor
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        user_id = 12345
        activity_type = 'message'
        timestamp = 1234567890
        
        # Call the function
        track_activity(user_id, activity_type, timestamp)

        # Assert that the database queries were called correctly
        mock_cursor.execute.assert_called_with(
            "INSERT INTO activity (user_id, activity_type, timestamp) VALUES (?, ?, ?)",
            (user_id, activity_type, timestamp)
        )
        mock_connect.return_value.commit.assert_called_once()

    @patch('db_server.sqlite3.connect')
    def test_check_boost_cooldown(self, mock_connect):
        # Mock the database connection and cursor
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        user_id = 12345

        # Mock the return value for checking cooldown
        mock_cursor.fetchone.return_value = (10,)  # Assume the user has 10 seconds left on cooldown
        
        # Call the function
        result = check_boost_cooldown(user_id)

        # Assert the result and the database query
        self.assertEqual(result, 10)
        mock_cursor.execute.assert_called_with(
            "SELECT cooldown FROM boost_cooldowns WHERE user_id = ?",
            (user_id,)
        )

    @patch('db_server.sqlite3.connect')
    def test_update_boost_cooldown(self, mock_connect):
        # Mock the database connection and cursor
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        user_id = 12345
        new_cooldown = 30  # Assume a 30-second cooldown
        
        # Call the function
        update_boost_cooldown(user_id, new_cooldown)

        # Assert that the database queries were called correctly
        mock_cursor.execute.assert_called_with(
            "INSERT INTO boost_cooldowns (user_id, cooldown) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET cooldown = ?",
            (user_id, new_cooldown, new_cooldown)
        )
        mock_connect.return_value.commit.assert_called_once()

    @patch('db_server.sqlite3.connect')
    def test_check_activity_burst(self, mock_connect):
        # Mock the database connection and cursor
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        user_id = 12345
        burst_threshold = 10  # Example burst threshold

        # Mock the return value for checking activity burst
        mock_cursor.fetchone.return_value = (15,)  # Assume the user has 15 activities in the burst period
        
        # Call the function
        result = check_activity_burst(user_id, burst_threshold)

        # Assert the result and the database query
        self.assertTrue(result)
        mock_cursor.execute.assert_called_with(
            "SELECT COUNT(*) FROM activity WHERE user_id = ? AND timestamp > ?",
            (user_id, burst_threshold)
        )

    @patch('db_server.sqlite3.connect')
    def test_delete_user_data(self, mock_connect):
        # Mock the database connection and cursor
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        user_id = 12345

        # Call the function
        delete_user_data(user_id)

        # Assert that the delete queries were called correctly
        mock_cursor.execute.assert_any_call("DELETE FROM user_xp WHERE user_id = ?", (user_id,))
        mock_cursor.execute.assert_any_call("DELETE FROM activity WHERE user_id = ?", (user_id,))
        mock_connect.return_value.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
