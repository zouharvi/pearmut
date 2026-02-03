"""Tests for dashboard data endpoint."""

from pearmut.app import app
from pearmut.utils import RESET_MARKER, _logs, save_db_payload


def _clear_test_logs():
    """Clear in-memory log cache."""
    _logs.clear()


class TestDashboardData:
    """Tests for dashboard data endpoint."""

    def test_single_stream_progress_counts(self):
        """Test that single-stream shows user-specific and global progress."""
        _clear_test_logs()
        
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Setup test data
        tasks_data = {
            "test_campaign": {
                "info": {
                    "assignment": "single-stream",
                },
                "token": "test_token",
                "data": [
                    [{"src": "a", "tgt": "b"}],
                    [{"src": "c", "tgt": "d"}],
                    [{"src": "e", "tgt": "f"}],
                ],
            }
        }

        progress_data = {
            "test_campaign": {
                "user1": {
                    "progress": [False, False, False],
                    "progress_welcome": [],
                    "time": 10,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                },
                "user2": {
                    "progress": [False, False, False],
                    "progress_welcome": [],
                    "time": 20,
                    "token_correct": "def",
                    "token_incorrect": "uvw",
                },
            }
        }

        # Mock the app's global state
        import pearmut.app as app_module

        app_module.tasks_data = tasks_data
        app_module.progress_data = progress_data

        # Add some annotations
        save_db_payload(
            "test_campaign", {"user_id": "user1", "item_i": 0, "annotation": {"score": 80}}
        )
        save_db_payload(
            "test_campaign", {"user_id": "user1", "item_i": 1, "annotation": {"score": 90}}
        )
        save_db_payload(
            "test_campaign", {"user_id": "user2", "item_i": 1, "annotation": {"score": 70}}
        )

        # Make request to dashboard-data endpoint
        response = client.post(
            "/dashboard-data",
            json={"campaign_id": "test_campaign", "token": "test_token"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["assignment"] == "single-stream"
        
        # User1 annotated 2 items (0 and 1)
        assert data["data"]["user1"]["finished_by_user"] == 2
        # User2 annotated 1 item (1)
        assert data["data"]["user2"]["finished_by_user"] == 1
        # Global: 2 unique items annotated (0 and 1)
        assert data["data"]["user1"]["global_progress"] == 2
        assert data["data"]["user2"]["global_progress"] == 2

    def test_dynamic_progress_counts(self):
        """Test that dynamic shows user-specific and global progress."""
        _clear_test_logs()
        
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Setup test data
        tasks_data = {
            "test_campaign_dyn": {
                "info": {
                    "assignment": "dynamic",
                    "dynamic_top": 2,
                    "dynamic_first": 5,
                },
                "token": "test_token",
                "data": [
                    [{"src": "a", "tgt": {"model1": "b", "model2": "c"}}],
                    [{"src": "d", "tgt": {"model1": "e", "model2": "f"}}],
                    [{"src": "g", "tgt": {"model1": "h", "model2": "i"}}],
                ],
            }
        }

        progress_data = {
            "test_campaign_dyn": {
                "user1": {
                    "progress": [[], [], []],
                    "progress_welcome": [],
                    "time": 10,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                },
                "user2": {
                    "progress": [[], [], []],
                    "progress_welcome": [],
                    "time": 20,
                    "token_correct": "def",
                    "token_incorrect": "uvw",
                },
            }
        }

        # Mock the app's global state
        import pearmut.app as app_module

        app_module.tasks_data = tasks_data
        app_module.progress_data = progress_data

        # Add some annotations
        save_db_payload(
            "test_campaign_dyn",
            {"user_id": "user1", "item_i": 0, "annotation": [{"model1": {"score": 80}}]},
        )
        save_db_payload(
            "test_campaign_dyn",
            {"user_id": "user1", "item_i": 2, "annotation": [{"model2": {"score": 90}}]},
        )
        save_db_payload(
            "test_campaign_dyn",
            {"user_id": "user2", "item_i": 0, "annotation": [{"model1": {"score": 70}}]},
        )

        # Make request to dashboard-data endpoint
        response = client.post(
            "/dashboard-data",
            json={"campaign_id": "test_campaign_dyn", "token": "test_token"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["assignment"] == "dynamic"
        
        # User1 annotated 2 items (0 and 2)
        assert data["data"]["user1"]["finished_by_user"] == 2
        # User2 annotated 1 item (0)
        assert data["data"]["user2"]["finished_by_user"] == 1
        # Global: 2 unique items annotated (0 and 2)
        assert data["data"]["user1"]["global_progress"] == 2
        assert data["data"]["user2"]["global_progress"] == 2

    def test_task_based_no_extra_fields(self):
        """Test that task-based does not add extra progress fields."""
        _clear_test_logs()
        
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Setup test data
        tasks_data = {
            "test_campaign_tb": {
                "info": {
                    "assignment": "task-based",
                },
                "token": "test_token",
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                        [{"src": "c", "tgt": "d"}],
                    ]
                },
            }
        }

        progress_data = {
            "test_campaign_tb": {
                "user1": {
                    "progress": [True, False],
                    "progress_welcome": [],
                    "time": 10,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }

        # Mock the app's global state
        import pearmut.app as app_module

        app_module.tasks_data = tasks_data
        app_module.progress_data = progress_data

        # Make request to dashboard-data endpoint
        response = client.post(
            "/dashboard-data",
            json={"campaign_id": "test_campaign_tb", "token": "test_token"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["assignment"] == "task-based"
        
        # Task-based should not have these fields
        assert "finished_by_user" not in data["data"]["user1"]
        assert "global_progress" not in data["data"]["user1"]

    def test_excludes_welcome_items_from_counts(self):
        """Test that welcome items are excluded from progress counts."""
        _clear_test_logs()
        
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Setup test data
        tasks_data = {
            "test_campaign_welcome": {
                "info": {
                    "assignment": "single-stream",
                },
                "token": "test_token",
                "data": [
                    [{"src": "a", "tgt": "b"}],
                    [{"src": "c", "tgt": "d"}],
                ],
            }
        }

        progress_data = {
            "test_campaign_welcome": {
                "user1": {
                    "progress": [False, False],
                    "progress_welcome": [False],
                    "time": 10,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }

        # Mock the app's global state
        import pearmut.app as app_module

        app_module.tasks_data = tasks_data
        app_module.progress_data = progress_data

        # Add annotations for welcome item and regular item
        save_db_payload(
            "test_campaign_welcome",
            {"user_id": "user1", "item_i": "welcome_0", "annotation": {"score": 80}},
        )
        save_db_payload(
            "test_campaign_welcome",
            {"user_id": "user1", "item_i": 0, "annotation": {"score": 90}},
        )

        # Make request to dashboard-data endpoint
        response = client.post(
            "/dashboard-data",
            json={"campaign_id": "test_campaign_welcome", "token": "test_token"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should count only regular items, not welcome items
        assert data["data"]["user1"]["finished_by_user"] == 1
        assert data["data"]["user1"]["global_progress"] == 1

    def test_excludes_reset_markers_from_counts(self):
        """Test that reset markers are excluded from progress counts."""
        _clear_test_logs()
        
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Setup test data
        tasks_data = {
            "test_campaign_reset": {
                "info": {
                    "assignment": "single-stream",
                },
                "token": "test_token",
                "data": [
                    [{"src": "a", "tgt": "b"}],
                    [{"src": "c", "tgt": "d"}],
                ],
            }
        }

        progress_data = {
            "test_campaign_reset": {
                "user1": {
                    "progress": [False, False],
                    "progress_welcome": [],
                    "time": 10,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }

        # Mock the app's global state
        import pearmut.app as app_module

        app_module.tasks_data = tasks_data
        app_module.progress_data = progress_data

        # Add annotation and then reset marker
        save_db_payload(
            "test_campaign_reset",
            {"user_id": "user1", "item_i": 0, "annotation": {"score": 80}},
        )
        save_db_payload(
            "test_campaign_reset",
            {"user_id": "user1", "item_i": 0, "annotation": RESET_MARKER},
        )

        # Make request to dashboard-data endpoint
        response = client.post(
            "/dashboard-data",
            json={"campaign_id": "test_campaign_reset", "token": "test_token"},
        )

        assert response.status_code == 200
        data = response.json()

        # Reset markers should not be counted
        assert data["data"]["user1"]["finished_by_user"] == 0
        assert data["data"]["user1"]["global_progress"] == 0
