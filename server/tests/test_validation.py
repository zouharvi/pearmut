"""Tests for campaign data validation."""


import pytest


class TestItemValidation:
    """Tests for item structure validation."""

    def test_valid_basic_task_based(self):
        """Test that valid basic task-based campaign passes validation."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_valid",
            "info": {
                "assignment": "task-based",
                "template": "basic",
                "shuffle": False,
            },
            "data": [
                [
                    [
                        {"src": "hello", "tgt": {"A": "hola", "B": "ola"}},
                        {"src": "world", "tgt": {"A": "mundo", "B": "munda"}}
                    ]
                ]
            ]
        }

        # Should not raise - use overwrite to avoid conflicts
        _add_single_campaign(campaign_data, True, "http://localhost:8001")



    def test_valid_singlestream(self):
        """Test that valid single-stream campaign passes validation."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_valid_ss",
            "info": {
                "assignment": "single-stream",
                "template": "basic",
                "users": 2,
                "shuffle": False,
            },
            "data": [
                [
                    {"src": "hello", "tgt": {"A": "hola", "B": "ola"}},
                    {"src": "world", "tgt": {"A": "mundo", "B": "munda"}}
                ]
            ]
        }

        # Should not raise - use overwrite to avoid conflicts
        _add_single_campaign(campaign_data, True, "http://localhost:8001")

    def test_missing_src_key(self):
        """Test that items without 'src' key are now allowed (src is optional)."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_missing_src",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    [
                        {"tgt": {"A": "hola"}}  # Missing 'src' - now allowed
                    ]
                ]
            ]
        }

        # This should NOT raise an error now since src is optional
        _add_single_campaign(campaign_data, True, "http://localhost:8001")

    def test_missing_tgt_key(self):
        """Test that items without 'tgt' key fail validation."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_missing_tgt",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    [
                        {"src": "hello"}  # Missing 'tgt'
                    ]
                ]
            ]
        }

        with pytest.raises(ValueError, match="must contain 'tgt' key"):
            _add_single_campaign(campaign_data, False, "http://localhost:8001")

    def test_item_not_dict(self):
        """Test that non-dict items fail validation."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_not_dict",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    [
                        "not a dict"  # Should be dict
                    ]
                ]
            ]
        }

        with pytest.raises(ValueError, match="must be a dictionary"):
            _add_single_campaign(campaign_data, False, "http://localhost:8001")

    def test_document_not_list(self):
        """Test that non-list documents fail validation."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_doc_not_list",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    {"src": "hello", "tgt": {"A": "hola"}}  # Should be list of items
                ]
            ]
        }

        with pytest.raises(ValueError, match="Items must be a list"):
            _add_single_campaign(campaign_data, False, "http://localhost:8001")

    def test_singlestream_missing_src(self):
        """Test that single-stream items without 'src' are now allowed (src is optional)."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_ss_missing_src",
            "info": {
                "assignment": "single-stream",
                "template": "basic",
                "users": 2,
            },
            "data": [
                [
                    {"tgt": {"A": "hola"}}  # Missing 'src' - now allowed
                ]
            ]
        }

        # This should NOT raise an error now since src is optional
        _add_single_campaign(campaign_data, True, "http://localhost:8001")

    def test_extra_keys_allowed(self):
        """Test that extra keys beyond src/tgt are allowed."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_extra_keys",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    [
                        {
                            "src": "hello",
                            "tgt": {"A": "hola", "B": "ola"},
                            "item_id": "123",
                            "model": "system1",
                            "instructions": "Translate this",
                            "validation": {"A": {"score": [70, 80]}}
                        }
                    ]
                ]
            ]
        }

        # Should not raise - extra keys are fine, use overwrite to avoid conflicts
        _add_single_campaign(campaign_data, True, "http://localhost:8001")

    def test_src_must_be_string(self):
        """Test that src must be a string."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_src_not_string",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    [
                        {"src": 123, "tgt": {"A": "hello"}}  # src is not a string
                    ]
                ]
            ]
        }

        with pytest.raises(ValueError, match="'src' must be a string"):
            _add_single_campaign(campaign_data, False, "http://localhost:8001")



    def test_tgt_must_be_dict_only(self):
        """Test that tgt must be a dictionary (no longer accepts strings)."""
        from pearmut.cli import _add_single_campaign

        # Test with string - should now fail with helpful error
        campaign_data = {
            "campaign_id": "test_tgt_string",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    [
                        {"src": "hello", "tgt": "single translation"}
                    ]
                ]
            ]
        }
        # Should fail with suggestion to use {"default": "..."}
        with pytest.raises(ValueError, match='For single translation, use \\{"default": "your_translation"\\}'):
            _add_single_campaign(campaign_data, True, "http://localhost:8001")
        
        # Test with invalid type - should fail
        campaign_data2 = {
            "campaign_id": "test_tgt_invalid",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    [
                        {"src": "hello", "tgt": 123}  # Invalid: number
                    ]
                ]
            ]
        }

        with pytest.raises(ValueError, match="'tgt' must be a dictionary mapping model names to translations"):
            _add_single_campaign(campaign_data2, False, "http://localhost:8001")

    def test_tgt_elements_must_be_strings(self):
        """Test that all elements in tgt list must be strings (basic template)."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_tgt_non_string_element",
            "info": {
                "assignment": "task-based",
                "template": "basic",
            },
            "data": [
                [
                    [
                        {"src": "hello", "tgt": {"A": "valid", "B": 123, "C": "another"}}
                    ]
                ]
            ]
        }

        with pytest.raises(ValueError, match="Translation for model 'B' must be a string"):
            _add_single_campaign(campaign_data, False, "http://localhost:8001")

    def test_basic_with_score_greaterthan_validation(self):
        """Test that basic template campaigns with score_greaterthan validation can be loaded."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_basic_score_greaterthan",
            "info": {
                "assignment": "task-based",
                "template": "basic",
                "protocol": "DA",
            },
            "data": [
                [
                    [
                        {
                            "src": "Test source text.",
                            "tgt": {"A": "Translation A", "B": "Translation B"},
                            "validation": {
                                "A": {
                                    "warning": "A must score higher than B.",
                                    "score": [80, 100],
                                    "score_greaterthan": "B"
                                },
                                "B": {
                                    "warning": "B should score lower.",
                                    "score": [40, 70]
                                }
                            }
                        }
                    ]
                ]
            ]
        }

        # Should not raise - the score_greaterthan field is valid
        _add_single_campaign(campaign_data, True, "http://localhost:8001")

    def test_custom_sliders_with_validation(self):
        """Test that campaigns with custom sliders and validation can be loaded."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_custom_sliders_validation",
            "info": {
                "assignment": "task-based",
                "template": "basic",
                "protocol": "DA",
                "sliders": [
                    {"name": "Fluency", "min": 0, "max": 5, "step": 1},
                    {"name": "Adequacy", "min": 0, "max": 100, "step": 1}
                ]
            },
            "data": [
                [
                    [
                        {
                            "src": "Test source text.",
                            "tgt": {"A": "Translation A"},
                            "validation": {
                                "A": {
                                    "warning": "Fluency should be 3-5, Adequacy 70-100",
                                    "Fluency": [3, 5],
                                    "Adequacy": [70, 100]
                                }
                            }
                        }
                    ]
                ]
            ]
        }

        # Should not raise - custom slider validation is valid
        _add_single_campaign(campaign_data, True, "http://localhost:8001")
