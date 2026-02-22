"""Tests for protocol functions."""

from pearmut.assignment import (
    get_i_item,
    get_next_item,
    reset_task,
    update_progress,
)
from pearmut.utils import (
    RESET_MARKER,
    _logs,
    check_validation_threshold,
    get_db_log_item,
    save_db_payload,
)


def _clear_test_logs():
    """Clear in-memory log cache and delete test log files for clean test state."""
    import glob
    import os

    from pearmut.utils import ROOT
    _logs.clear()
    # Also delete any test log files
    for log_file in glob.glob(f"{ROOT}/data/outputs/*.jsonl"):
        try:
            os.remove(log_file)
        except OSError:
            pass


class TestTaskBased:
    """Tests for task-based assignment."""

    def test_get_next_item_returns_first_incomplete(self):
        """Test that task-based returns the first incomplete item."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "shuffle": False,
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                        [{"src": "c", "tgt": "d"}],
                        [{"src": "e", "tgt": "f"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed", None, None],
                    "progress_welcome": [],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"item_i":1' in content

    def test_get_next_item_completed_returns_token(self):
        """Test that task-based returns completion token when all items done."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "shuffle": False,
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed"],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        assert 'correct_token' in content

    def test_update_progress_marks_item_complete(self):
        """Test that update_progress marks the item as complete."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "shuffle": False,
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [None, None, None],
                    "progress_welcome": [],
                }
            }
        }
        update_progress("campaign1", "user1", tasks_data, progress_data, 1, {})
        assert progress_data["campaign1"]["user1"]["progress"] == [
            None, "completed", None]

    def test_reset_task_clears_progress(self):
        """Test that reset_task clears the progress."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                        [{"src": "c", "tgt": "d"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed", "completed"],
                    "progress_welcome": [],
                    "time": 100.0,
                    "time_start": 1000,
                    "time_end": 2000,
                }
            }
        }
        reset_task("campaign1", "user1", tasks_data, progress_data)
        assert progress_data["campaign1"]["user1"]["progress"] == [
            None, None]
        assert progress_data["campaign1"]["user1"]["time"] == 0.0
        assert progress_data["campaign1"]["user1"]["time_start"] is None
        assert progress_data["campaign1"]["user1"]["time_end"] is None

    def test_get_i_item_returns_specific_item(self):
        """Test that task-based get_i_item returns the requested item."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                        [{"src": "c", "tgt": "d"}],
                        [{"src": "e", "tgt": "f"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed", None, None],
                    "progress_welcome": [],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        # Request item 2 specifically
        response = get_i_item("campaign1", "user1",
                              tasks_data, progress_data, 2)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"item_i":2' in content
        assert '"src":"e"' in content

    def test_get_i_item_out_of_range(self):
        """Test that task-based get_i_item returns error for invalid index."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [None],
                    "progress_welcome": [],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        response = get_i_item("campaign1", "user1",
                              tasks_data, progress_data, 10)
        assert response.status_code == 400
        content = response.body.decode()
        assert 'out of range' in content

    def test_instructions_goodbye_default(self):
        """Test that default instructions_goodbye message is used when not specified."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed"],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "CORRECT_TOKEN",
                    "token_incorrect": "WRONG_TOKEN",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        # Check default message with token replacement
        assert 'If someone asks you for a token of completion' in content
        assert 'CORRECT_TOKEN' in content

    def test_instructions_goodbye_custom(self):
        """Test that custom instructions_goodbye message with variables is used."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "instructions_goodbye": "Thank you ${USER_ID}! Your completion code is: <b>${TOKEN}</b>"
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed"],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "MY_TOKEN",
                    "token_incorrect": "BAD_TOKEN",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        # Check custom message with variable replacement
        assert 'Thank you user1!' in content
        assert '<b>MY_TOKEN</b>' in content
        assert 'BAD_TOKEN' not in content

    def test_instructions_goodbye_incorrect_token(self):
        """Test that instructions_goodbye uses incorrect token when validation fails."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 0,  # Fail on any validation failure
                    "instructions_goodbye": "Code: ${TOKEN}"
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed"],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "PASS_TOKEN",
                    "token_incorrect": "FAIL_TOKEN",
                    "validations": {
                        0: [False]  # Failed validation
                    }
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        # Should use incorrect token
        assert 'FAIL_TOKEN' in content
        assert 'PASS_TOKEN' not in content

    def test_instructions_goodbye_html_injection(self):
        """Test that HTML can be injected in instructions_goodbye via variables."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "instructions_goodbye": "User: ${USER_ID}, Token: ${TOKEN}"
                },
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}],
                    ]
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed"],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "<b>MY_TOKEN</b>",
                    "token_incorrect": "BAD_TOKEN",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        # Check that HTML is NOT escaped - raw HTML should appear in instructions_goodbye
        assert '<b>MY_TOKEN</b>' in content
        assert 'User: user1, Token: <b>MY_TOKEN</b>' in content


class TestSingleStream:
    """Tests for single-stream assignment."""

    def test_get_next_item_returns_random_incomplete(self):
        """Test that single-stream returns a random incomplete item."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "single-stream",
                    "shuffle": False,
                },
                "data": [
                    [{"src": "a", "tgt": "b"}],
                    [{"src": "c", "tgt": "d"}],
                    [{"src": "e", "tgt": "f"}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed", None, None],
                    "progress_welcome": [],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        # Should return item 1 or 2 (incomplete items)
        assert '"item_i":1' in content or '"item_i":2' in content

    def test_singlestream_completed_returns_token(self):
        """Test that single-stream returns completion token when all items done."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "single-stream",
                },
                "data": [
                    [{"src": "a", "tgt": "b"}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed"],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        assert 'correct_token' in content

    def test_reset_task_resets_completed_items_for_all_users(self):
        """Test that single-stream reset_task resets items the user originally completed, for all users in the shared pool."""
        _clear_test_logs()
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "single-stream",
                },
                "data": [
                    [{"src": "a", "tgt": "b"}],
                    [{"src": "c", "tgt": "d"}],
                    [{"src": "e", "tgt": "f"}],
                    [{"src": "g", "tgt": "h"}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed", None, "completed_foreign", "completed"],
                    "progress_welcome": [],
                    "time": 50.0,
                    "time_start": 1000,
                    "time_end": 2000,
                    "validations": {},
                },
                "user2": {
                    "progress": ["completed", None, "completed", "completed_foreign"],
                    "progress_welcome": [],
                    "time": 75.0,
                    "time_start": 1100,
                    "time_end": 2100,
                    "validations": {},
                }
            }
        }
        # Add annotations for user1 on items 0 and 3
        save_db_payload("campaign1", {
            "user_id": "user1",
            "item_i": 0,
            "annotation": {"score": 80}
        })
        save_db_payload("campaign1", {
            "user_id": "user1",
            "item_i": 3,
            "annotation": {"score": 90}
        })
        # Add annotation for user2 on items 0 and 2
        save_db_payload("campaign1", {
            "user_id": "user2",
            "item_i": 0,
            "annotation": {"score": 70}
        })
        save_db_payload("campaign1", {
            "user_id": "user2",
            "item_i": 2,
            "annotation": {"score": 85}
        })

        reset_task("campaign1", "user1", tasks_data, progress_data)

        # Items user1 originally completed (0 and 3) are reset for both users in the shared pool
        # Item 2 was completed_foreign for user1 (not originally theirs) so it is NOT reset
        assert progress_data["campaign1"]["user1"]["progress"] == [None, None, "completed_foreign", None]
        # User2's items 0 and 3 are also reset (shared pool), item 2 is unaffected
        assert progress_data["campaign1"]["user2"]["progress"] == [None, None, "completed", None]
        # Only user1's time should be reset
        assert progress_data["campaign1"]["user1"]["time"] == 0.0
        assert progress_data["campaign1"]["user1"]["time_start"] is None
        assert progress_data["campaign1"]["user2"]["time"] == 75.0

        # User1's annotations on items 0 and 3 should be masked
        assert len(get_db_log_item("campaign1", "user1", 0)) == 0
        assert len(get_db_log_item("campaign1", "user1", 3)) == 0

        # User2's annotations are unaffected (different user_id in the log)
        items_user2_0 = get_db_log_item("campaign1", "user2", 0)
        assert len(items_user2_0) == 1
        assert items_user2_0[0]["annotation"] == {"score": 70}

        items_user2_2 = get_db_log_item("campaign1", "user2", 2)
        assert len(items_user2_2) == 1
        assert items_user2_2[0]["annotation"] == {"score": 85}

    def test_update_progress_updates_all_users(self):
        """Test that single-stream update_progress updates all users."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "single-stream",
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [None, None, None],
                    "progress_welcome": [],
                },
                "user2": {
                    "progress": [None, None, None],
                    "progress_welcome": [],
                }
            }
        }
        update_progress("campaign1", "user1", tasks_data, progress_data, 1, {})
        # User1 completed item 1, so gets "completed"
        # User2 gets "completed_foreign" since someone else completed it
        assert progress_data["campaign1"]["user1"]["progress"] == [None, "completed", None]
        assert progress_data["campaign1"]["user2"]["progress"] == [None, "completed_foreign", None]

    def test_get_i_item_returns_specific_item(self):
        """Test that single-stream get_i_item returns the requested item."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "single-stream",
                },
                "data": [
                    [{"src": "a", "tgt": "b"}],
                    [{"src": "c", "tgt": "d"}],
                    [{"src": "e", "tgt": "f"}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed", None, None],
                    "progress_welcome": [],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        # Request item 2 specifically
        response = get_i_item("campaign1", "user1", tasks_data, progress_data, 2)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"item_i":2' in content
        assert '"src":"e"' in content

    def test_docs_per_user_triggers_goodbye(self):
        """Test that single-stream with docs_per_user shows goodbye after specified items."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "single-stream",
                    "docs_per_user": 2,
                },
                "data": [
                    [{"src": "a", "tgt": "b"}],
                    [{"src": "c", "tgt": "d"}],
                    [{"src": "e", "tgt": "f"}],
                    [{"src": "g", "tgt": "h"}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed", None, "completed", None],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        # User has completed 2 items (indices 0 and 2), should get goodbye
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        assert 'correct_token' in content

    def test_docs_per_user_continues_before_limit(self):
        """Test that single-stream continues returning items before docs_per_user limit."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "single-stream",
                    "docs_per_user": 3,
                },
                "data": [
                    [{"src": "a", "tgt": "b"}],
                    [{"src": "c", "tgt": "d"}],
                    [{"src": "e", "tgt": "f"}],
                    [{"src": "g", "tgt": "h"}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": ["completed", None, "completed", None],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        # User has completed 2 items, limit is 3, should get next item
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"ok"' in content
        # Should return one of the incomplete items (1 or 3)
        assert '"item_i":1' in content or '"item_i":3' in content

    def test_get_next_item_returns_welcome_data_during_tutorial(self):
        """Test that single-stream returns data_welcome items (not data) during tutorial."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "single-stream",
                },
                "data_welcome": [
                    [{"src": "tutorial_src", "tgt": {"A": "tutorial_tgt"}}],
                ],
                "data": [
                    [{"src": "real_src", "tgt": {"A": "real_tgt"}}],
                ],
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [None],
                    "progress_welcome": [False],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        # Should return welcome item, not regular data item
        assert "tutorial_src" in content
        assert "real_src" not in content
        assert '"item_i":"welcome_0"' in content

class TestResetMasking:
    """Tests for reset masking functionality."""

    def test_reset_marker_masks_existing_annotations(self):
        """Test that reset marker masks all existing annotations."""
        _clear_test_logs()
        campaign_id = "test_campaign_reset"

        # Save some annotations
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": 0,
            "annotation": {"score": 80}
        })
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": 0,
            "annotation": {"score": 90}
        })

        # Verify annotations exist
        items = get_db_log_item(campaign_id, "user1", 0)
        assert len(items) == 2

        # Save reset marker
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": 0,
            "annotation": RESET_MARKER
        })

        # Verify annotations are masked (no items returned after reset)
        items = get_db_log_item(campaign_id, "user1", 0)
        assert len(items) == 0

    def test_annotations_after_reset_are_visible(self):
        """Test that annotations after reset marker are visible."""
        _clear_test_logs()
        campaign_id = "test_campaign_after_reset"

        # Save old annotations
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": 0,
            "annotation": {"score": 50}
        })

        # Save reset marker
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": 0,
            "annotation": RESET_MARKER
        })

        # Save new annotations after reset
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": 0,
            "annotation": {"score": 75}
        })

        # Verify only new annotations are visible
        items = get_db_log_item(campaign_id, "user1", 0)
        assert len(items) == 1
        assert items[0]["annotation"] == {"score": 75}

    def test_reset_marker_per_user_isolation(self):
        """Test that reset markers only affect the specific user."""
        _clear_test_logs()
        campaign_id = "test_campaign_user_isolation"

        # Save annotations for user1 and user2
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": 0,
            "annotation": {"score": 60}
        })
        save_db_payload(campaign_id, {
            "user_id": "user2",
            "item_i": 0,
            "annotation": {"score": 70}
        })

        # Reset only user1
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": 0,
            "annotation": RESET_MARKER
        })

        # User1 should have no annotations
        items_user1 = get_db_log_item(campaign_id, "user1", 0)
        assert len(items_user1) == 0

        # User2 should still have annotations
        items_user2 = get_db_log_item(campaign_id, "user2", 0)
        assert len(items_user2) == 1
        assert items_user2[0]["annotation"] == {"score": 70}

    def test_reset_task_clears_welcome_form_data(self):
        """Test that reset_task clears welcome form data by saving reset markers."""
        _clear_test_logs()
        campaign_id = "test_welcome_form_reset"
        
        tasks_data = {
            campaign_id: {
                "info": {
                    "assignment": "task-based",
                    "protocol": "DA",
                },
                "data_welcome": [
                    [
                        {"text": "Name", "form": "string"},
                        {"text": "Age", "form": "number"}
                    ]
                ],
                "data": {
                    "user1": [
                        [{"src": "a", "tgt": "b"}]
                    ]
                },
                "token": "test_token"
            }
        }
        
        progress_data = {
            campaign_id: {
                "user1": {
                    "progress": [None],
                    "progress_welcome": [False],
                    "time": 0,
                    "time_start": None,
                    "time_end": None,
                    "validations": {}
                }
            }
        }
        
        # User fills out welcome form
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": "welcome_0",
            "annotation": ["John", 30]
        })
        
        # Verify form data exists
        items = get_db_log_item(campaign_id, "user1", "welcome_0")
        assert len(items) == 1
        assert items[0]["annotation"] == ["John", 30]
        
        # Reset task
        reset_task(campaign_id, "user1", tasks_data, progress_data)
        
        # Verify welcome form data is masked
        items = get_db_log_item(campaign_id, "user1", "welcome_0")
        assert len(items) == 0

    def test_reset_task_single_stream_only_resets_completed_welcome_items(self):
        """Test that reset_task in single-stream only saves reset markers for completed welcome items."""
        _clear_test_logs()
        campaign_id = "test_singlestream_welcome_reset"
        
        tasks_data = {
            campaign_id: {
                "info": {
                    "assignment": "single-stream",
                    "protocol": "DA",
                },
                "data_welcome": [
                    [
                        {"text": "Name", "form": "string"},
                        {"text": "Age", "form": "number"}
                    ],
                    [
                        {"text": "Country", "form": "string"}
                    ]
                ],
                "data": [
                    [{"src": "a", "tgt": {"A": "b"}}]
                ],
                "token": "test_token"
            }
        }
        
        progress_data = {
            campaign_id: {
                "user1": {
                    "progress": [None],
                    "progress_welcome": ["completed", False],  # First completed, second not
                    "time": 0,
                    "time_start": None,
                    "time_end": None,
                    "validations": {}
                }
            }
        }
        
        # User fills out both welcome forms
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": "welcome_0",
            "annotation": ["Alice", 25]
        })
        save_db_payload(campaign_id, {
            "user_id": "user1",
            "item_i": "welcome_1",
            "annotation": ["USA"]
        })
        
        # Verify both have data
        items0 = get_db_log_item(campaign_id, "user1", "welcome_0")
        items1 = get_db_log_item(campaign_id, "user1", "welcome_1")
        assert len(items0) == 1
        assert len(items1) == 1
        
        # Reset task
        reset_task(campaign_id, "user1", tasks_data, progress_data)
        
        # Verify only completed welcome item (welcome_0) is masked
        items0 = get_db_log_item(campaign_id, "user1", "welcome_0")
        items1 = get_db_log_item(campaign_id, "user1", "welcome_1")
        assert len(items0) == 0, "Completed welcome item should be masked after reset"
        assert len(items1) == 1, "Uncompleted welcome item should NOT be masked after reset"


class TestValidationThreshold:
    """Tests for validation threshold functionality."""

    def test_no_threshold_defaults_to_zero(self):
        """Test that no threshold defaults to 0 (fail on any failure)."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    # No validation_threshold set - defaults to 0
                }
            }
        }
        # With failures, should fail (threshold defaults to 0)
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {
                        0: [False, None, None],  # All failed
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is False
        
        # With all passed, should pass
        progress_data["campaign1"]["user1"]["validations"][0] = [True, True, True]
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

    def test_integer_threshold_zero_fails_on_any_failure(self):
        """Test that threshold 0 fails if there's any failed check."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 0,
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {
                        0: [True, False, True],  # 1 failed
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is False

    def test_integer_threshold_zero_passes_on_all_success(self):
        """Test that threshold 0 passes if all checks pass."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 0,
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {
                        0: [True, True, True],  # All passed
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

    def test_integer_threshold_allows_failures_up_to_limit(self):
        """Test that integer threshold allows failures up to the limit."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 2,
                }
            }
        }
        # 2 failures should pass
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {
                        0: [True, None, None],  # 2 failed
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

        # 3 failures should fail
        progress_data["campaign1"]["user1"]["validations"][0] = [False, None, None]
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is False

    def test_float_threshold_proportion_based(self):
        """Test that float threshold is proportion-based."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 0.5,  # Allow up to 50% failures
                }
            }
        }
        # 1/4 = 25% failed should pass
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {
                        0: [True, True, True, False],  # 1/4 = 25% failed
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

        # 3/4 = 75% failed should fail
        progress_data["campaign1"]["user1"]["validations"][0] = [None, None, None, "completed"]
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is False

    def test_float_threshold_zero_proportion_based(self):
        """Test that float 0.0 threshold is proportion-based (0% failures allowed)."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 0.0,  # 0% failures allowed (same as 0 integer)
                }
            }
        }
        # All passed should pass
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {
                        0: [True, True, True],
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

        # Any failure should fail (0% proportion exceeded)
        progress_data["campaign1"]["user1"]["validations"][0] = [True, True, False]
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is False

    def test_float_threshold_above_one_always_fails(self):
        """Test that float threshold >= 1 always fails."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 1.5,  # Above 1, always fail
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {
                        0: [True, True, True],  # All passed, but threshold >= 1 should still fail
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is False

    def test_empty_validations_passes(self):
        """Test that no validations means pass."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 0,
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {}
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

    def test_missing_validations_passes(self):
        """Test that missing validations key means pass."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 0,
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    # No validations key
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

    def test_multiple_items_aggregated(self):
        """Test that validations from multiple items are aggregated."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "task-based",
                    "validation_threshold": 2,  # Allow up to 2 failures
                }
            }
        }
        # 1 failure in item 0, 1 failure in item 1 = 2 total failures
        progress_data = {
            "campaign1": {
                "user1": {
                    "validations": {
                        0: [True, False],  # 1 failed
                        1: [False, True],  # 1 failed
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

        # Add another failure to exceed threshold
        progress_data["campaign1"]["user1"]["validations"][2] = [False]
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is False


class TestDynamic:
    """Tests for dynamic assignment."""

    def test_get_next_item_returns_item_from_pool(self):
        """Test that dynamic returns an item from the shared pool."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "dynamic",
                    "shuffle": False,
                    "dynamic_top": 1,
                    "dynamic_warmup": 2,
                    "dynamic_backoff": 0,
                },
                "data": [
                    [{"src": "a", "tgt": {"model1": "b", "model2": "c"}}],
                    [{"src": "d", "tgt": {"model1": "e", "model2": "f"}}],
                    [{"src": "g", "tgt": {"model1": "h", "model2": "i"}}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [{"model1": None, "model2": None}, {"model1": None, "model2": None}, {"model1": None, "model2": None}],
                    "progress_welcome": [],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        # Should return one of the incomplete items
        assert '"item_i":0' in content or '"item_i":1' in content or '"item_i":2' in content

    def test_dynamic_completed_returns_token(self):
        """Test that dynamic returns completion token when all items done."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "dynamic",
                    "shuffle": False,
                    "dynamic_top": 1,
                    "dynamic_warmup": 2,
                },
                "data": [
                    [{"src": "a", "tgt": {"model1": "b"}}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [{"model1": "completed", "model2": "completed"}],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        assert 'correct_token' in content

    def test_update_progress_updates_all_users(self):
        """Test that dynamic update_progress updates all users."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "dynamic",
                }
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [{"model1": None, "model2": None}, {"model1": None, "model2": None}, {"model1": None, "model2": None}],
                    "progress_welcome": [],
                },
                "user2": {
                    "progress": [{"model1": None, "model2": None}, {"model1": None, "model2": None}, {"model1": None, "model2": None}],
                    "progress_welcome": [],
                }
            }
        }
        # Simulate an annotation with model1
        payload = {"annotation": [{"model1": {"score": 5}}]}
        update_progress("campaign1", "user1", tasks_data, progress_data, 1, payload)
        # User1 completed item 1, user2 gets completed_foreign
        assert progress_data["campaign1"]["user1"]["progress"][1]["model1"] == "completed"
        assert progress_data["campaign1"]["user2"]["progress"][1]["model1"] == "completed_foreign"
        assert progress_data["campaign1"]["user1"]["progress"][0]["model1"] is None
        assert progress_data["campaign1"]["user2"]["progress"][0]["model1"] is None

    def test_reset_task_resets_only_requesting_user(self):
        """Test that dynamic reset_task resets only the requesting user's completed items."""
        _clear_test_logs()
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "dynamic",
                },
                "data": [
                    [{"src": "a", "tgt": {"model1": "b"}}],
                    [{"src": "c", "tgt": {"model1": "d"}}],
                    [{"src": "e", "tgt": {"model1": "f"}}],
                    [{"src": "g", "tgt": {"model1": "h"}}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [{"model1": "completed"}, {"model1": "completed"}, {"model1": None}, {"model1": "completed"}],
                    "progress_welcome": [],
                    "time": 50.0,
                    "time_start": 1000,
                    "time_end": 2000,
                    "validations": {},
                },
                "user2": {
                    "progress": [{"model1": "completed"}, {"model1": "completed"}, {"model1": "completed"}, {"model1": None}],
                    "progress_welcome": [],
                    "time": 75.0,
                    "time_start": 1100,
                    "time_end": 2100,
                    "validations": {},
                }
            }
        }
        # Add annotations for user1 on items 0, 1, 3
        save_db_payload("campaign1", {"user_id": "user1", "item_i": 0, "annotation": [{"model1": {"score": 5}}]})
        save_db_payload("campaign1", {"user_id": "user1", "item_i": 1, "annotation": [{"model1": {"score": 4}}]})
        save_db_payload("campaign1", {"user_id": "user1", "item_i": 3, "annotation": [{"model1": {"score": 3}}]})

        response = reset_task("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200

        # User1's completed items (0, 1, 3) reset to None; item 2 was already None
        assert progress_data["campaign1"]["user1"]["progress"] == [
            {"model1": None}, {"model1": None}, {"model1": None}, {"model1": None}]
        # User2's progress is entirely unchanged
        assert progress_data["campaign1"]["user2"]["progress"] == [
            {"model1": "completed"}, {"model1": "completed"}, {"model1": "completed"}, {"model1": None}]
        # Only user1's time should be reset
        assert progress_data["campaign1"]["user1"]["time"] == 0.0
        assert progress_data["campaign1"]["user1"]["time_start"] is None
        assert progress_data["campaign1"]["user2"]["time"] == 75.0

        # User1's annotations should be masked
        assert len(get_db_log_item("campaign1", "user1", 0)) == 0
        assert len(get_db_log_item("campaign1", "user1", 1)) == 0
        assert len(get_db_log_item("campaign1", "user1", 3)) == 0

    def test_docs_per_user_triggers_goodbye(self):
        """Test that dynamic with docs_per_user shows goodbye after specified items."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "dynamic",
                    "docs_per_user": 2,
                    "dynamic_top": 1,
                    "dynamic_first": 2,
                },
                "data": [
                    [{"src": "a", "tgt": {"model1": "b", "model2": "c"}}],
                    [{"src": "d", "tgt": {"model1": "e", "model2": "f"}}],
                    [{"src": "g", "tgt": {"model1": "h", "model2": "i"}}],
                    [{"src": "j", "tgt": {"model1": "k", "model2": "l"}}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [{"model1": "completed", "model2": None}, {"model1": None, "model2": None}, {"model1": None, "model2": "completed"}, {"model1": None, "model2": None}],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        # User has completed 2 items (indices 0 and 2 have annotations), should get goodbye
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        assert 'correct_token' in content

    def test_docs_per_user_continues_before_limit(self):
        """Test that dynamic continues returning items before docs_per_user limit."""
        tasks_data = {
            "campaign1": {
                "info": {
                    "assignment": "dynamic",
                    "docs_per_user": 3,
                    "dynamic_top": 1,
                    "dynamic_first": 2,
                },
                "data": [
                    [{"src": "a", "tgt": {"model1": "b", "model2": "c"}}],
                    [{"src": "d", "tgt": {"model1": "e", "model2": "f"}}],
                    [{"src": "g", "tgt": {"model1": "h", "model2": "i"}}],
                    [{"src": "j", "tgt": {"model1": "k", "model2": "l"}}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [{"model1": "completed", "model2": None}, {"model1": None, "model2": None}, {"model1": "completed", "model2": None}, {"model1": None, "model2": None}],
                    "progress_welcome": [],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        # User has completed 2 items, limit is 3, should get next item
        response = get_next_item("campaign1", "user1", tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"ok"' in content
        # Should return an item
        assert '"item_i"' in content

