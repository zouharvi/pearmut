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
    import os
    import glob
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
                    "progress": [True, False, False],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "progress": [True],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "progress": [False, False, False],
                }
            }
        }
        update_progress("campaign1", "user1", tasks_data, progress_data, 1, {})
        assert progress_data["campaign1"]["user1"]["progress"] == [
            False, True, False]

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
                    "progress": [True, True],
                    "time": 100.0,
                    "time_start": 1000,
                    "time_end": 2000,
                }
            }
        }
        reset_task("campaign1", "user1", tasks_data, progress_data)
        assert progress_data["campaign1"]["user1"]["progress"] == [
            False, False]
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
                    "progress": [True, False, False],
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
                    "progress": [False],
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
                    "progress": [True],
                    "time": 100,
                    "token_correct": "CORRECT_TOKEN",
                    "token_incorrect": "WRONG_TOKEN",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "progress": [True],
                    "time": 100,
                    "token_correct": "MY_TOKEN",
                    "token_incorrect": "BAD_TOKEN",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "progress": [True],
                    "time": 100,
                    "token_correct": "PASS_TOKEN",
                    "token_incorrect": "FAIL_TOKEN",
                    "validations": {
                        0: [False]  # Failed validation
                    }
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "progress": [True],
                    "time": 100,
                    "token_correct": "<b>MY_TOKEN</b>",
                    "token_incorrect": "BAD_TOKEN",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "progress": [True, False, False],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "progress": [True],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
        assert response.status_code == 200
        content = response.body.decode()
        assert '"status":"goodbye"' in content
        assert 'correct_token' in content

    def test_reset_task_resets_all_users(self):
        """Test that single-stream reset_task resets only touched items for all users."""
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
                    "progress": [True, True, False, True],
                    "time": 50.0,
                    "time_start": 1000,
                    "time_end": 2000,
                    "validations": {},
                },
                "user2": {
                    "progress": [True, True, True, False],
                    "time": 75.0,
                    "time_start": 1100,
                    "time_end": 2100,
                    "validations": {},
                }
            }
        }
        # Add annotations for user1 on items 0 and 1
        save_db_payload("campaign1", {
            "user_id": "user1",
            "item_i": 0,
            "annotation": {"score": 80}
        })
        save_db_payload("campaign1", {
            "user_id": "user1",
            "item_i": 1,
            "annotation": {"score": 90}
        })
        # Add annotation for user2 on item 0 and 2
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
        
        # Only items touched by user1 (0 and 1) should be reset for all users
        # Items 2 and 3 should remain unchanged
        assert progress_data["campaign1"]["user1"]["progress"] == [
            False, False, False, True]
        assert progress_data["campaign1"]["user2"]["progress"] == [
            False, False, True, False]
        # Only user1's time should be reset
        assert progress_data["campaign1"]["user1"]["time"] == 0.0
        assert progress_data["campaign1"]["user1"]["time_start"] is None
        assert progress_data["campaign1"]["user2"]["time"] == 75.0
        
        # Verify reset markers were added only for user1's items (0 and 1)
        items_user1_0 = get_db_log_item("campaign1", "user1", 0)
        items_user1_1 = get_db_log_item("campaign1", "user1", 1)
        assert len(items_user1_0) == 0  # Masked by reset marker
        assert len(items_user1_1) == 0  # Masked by reset marker
        
        # User2's annotation on item 0 should still be visible (different user_id)
        items_user2_0 = get_db_log_item("campaign1", "user2", 0)
        assert len(items_user2_0) == 1
        assert items_user2_0[0]["annotation"] == {"score": 70}
        
        # User2's annotation on item 2 should still be visible (user1 didn't touch it)
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
                    "progress": [False, False, False],
                },
                "user2": {
                    "progress": [False, False, False],
                }
            }
        }
        update_progress("campaign1", "user1", tasks_data, progress_data, 1, {})
        # Both users should have item 1 marked as complete
        assert progress_data["campaign1"]["user1"]["progress"] == [
            False, True, False]
        assert progress_data["campaign1"]["user2"]["progress"] == [
            False, True, False]

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
                    "progress": [True, False, False],
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
                        0: [False, False, False],  # All failed
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
                        0: [True, False, False],  # 2 failed
                    }
                }
            }
        }
        assert check_validation_threshold(tasks_data, progress_data, "campaign1", "user1") is True

        # 3 failures should fail
        progress_data["campaign1"]["user1"]["validations"][0] = [False, False, False]
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
        progress_data["campaign1"]["user1"]["validations"][0] = [False, False, False, True]
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
                    "dynamic_first": 2,
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
                    "progress": [list(), list(), list()],
                    "time": 0,
                    "token_correct": "abc",
                    "token_incorrect": "xyz",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "dynamic_first": 2,
                },
                "data": [
                    [{"src": "a", "tgt": {"model1": "b"}}],
                ]
            }
        }
        progress_data = {
            "campaign1": {
                "user1": {
                    "progress": [{"model1"}],
                    "time": 100,
                    "token_correct": "correct_token",
                    "token_incorrect": "wrong_token",
                }
            }
        }
        response = get_next_item("campaign1", "user1",
                                 tasks_data, progress_data)
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
                    "progress": [list(), list(), list()],
                },
                "user2": {
                    "progress": [list(), list(), list()],
                }
            }
        }
        # Simulate an annotation with model1
        payload = {"annotation": [{"model1": {"score": 5}}]}
        update_progress("campaign1", "user1", tasks_data, progress_data, 1, payload)
        # Both users should have model1 tracked for item 1
        assert "model1" in progress_data["campaign1"]["user1"]["progress"][1]
        assert "model1" in progress_data["campaign1"]["user2"]["progress"][1]
        assert progress_data["campaign1"]["user1"]["progress"][0] == list()
        assert progress_data["campaign1"]["user2"]["progress"][0] == list()

    def test_reset_task_resets_all_users(self):
        """Test that dynamic reset_task resets only touched items for all users."""
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
                    "progress": [{"model1"}, {"model1"}, list(), {"model1"}],
                    "time": 50.0,
                    "time_start": 1000,
                    "time_end": 2000,
                    "validations": {},
                },
                "user2": {
                    "progress": [{"model1"}, {"model1"}, {"model1"}, list()],
                    "time": 75.0,
                    "time_start": 1100,
                    "time_end": 2100,
                    "validations": {},
                }
            }
        }
        # Add annotations for user1 on items 0 and 1
        save_db_payload("campaign1", {
            "user_id": "user1",
            "item_i": 0,
            "annotation": [{"model1": {"score": 80}}]
        })
        save_db_payload("campaign1", {
            "user_id": "user1",
            "item_i": 1,
            "annotation": [{"model1": {"score": 90}}]
        })
        # Add annotation for user2 on item 0 and 2
        save_db_payload("campaign1", {
            "user_id": "user2",
            "item_i": 0,
            "annotation": [{"model1": {"score": 70}}]
        })
        save_db_payload("campaign1", {
            "user_id": "user2",
            "item_i": 2,
            "annotation": [{"model1": {"score": 85}}]
        })
        
        reset_task("campaign1", "user1", tasks_data, progress_data)
        
        # Only items touched by user1 (0 and 1) should be reset for all users
        # Items 2 and 3 should remain unchanged
        assert progress_data["campaign1"]["user1"]["progress"] == [
            list(), list(), list(), {"model1"}]
        assert progress_data["campaign1"]["user2"]["progress"] == [
            list(), list(), {"model1"}, list()]
        # Only user1's time should be reset
        assert progress_data["campaign1"]["user1"]["time"] == 0.0
        assert progress_data["campaign1"]["user1"]["time_start"] is None
        assert progress_data["campaign1"]["user2"]["time"] == 75.0
        
        # Verify reset markers were added only for user1's items (0 and 1)
        items_user1_0 = get_db_log_item("campaign1", "user1", 0)
        items_user1_1 = get_db_log_item("campaign1", "user1", 1)
        assert len(items_user1_0) == 0  # Masked by reset marker
        assert len(items_user1_1) == 0  # Masked by reset marker
        
        # User2's annotation on item 0 should still be visible (different user_id)
        items_user2_0 = get_db_log_item("campaign1", "user2", 0)
        assert len(items_user2_0) == 1
        assert items_user2_0[0]["annotation"] == [{"model1": {"score": 70}}]
        
        # User2's annotation on item 2 should still be visible (user1 didn't touch it)
        items_user2_2 = get_db_log_item("campaign1", "user2", 2)
        assert len(items_user2_2) == 1
        assert items_user2_2[0]["annotation"] == [{"model1": {"score": 85}}]
