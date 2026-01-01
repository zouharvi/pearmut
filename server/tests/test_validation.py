"""Tests for campaign data validation."""

import json
import os
import tempfile

import pytest


class TestItemValidation:
    """Tests for item structure validation."""

    def test_valid_basic_task_based(self):
        """Test that valid basic task-based campaign passes validation."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            # Should not raise - use overwrite to avoid conflicts
            _add_single_campaign(campaign_file, True, "http://localhost:8001")



    def test_valid_singlestream(self):
        """Test that valid single-stream campaign passes validation."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            # Should not raise - use overwrite to avoid conflicts
            _add_single_campaign(campaign_file, True, "http://localhost:8001")

    def test_missing_src_key(self):
        """Test that items without 'src' key fail validation."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
                    "campaign_id": "test_missing_src",
                    "info": {
                        "assignment": "task-based",
                        "template": "basic",
                    },
                    "data": [
                        [
                            [
                                {"tgt": {"A": "hola"}}  # Missing 'src'
                            ]
                        ]
                    ]
                }, f)

            with pytest.raises(ValueError, match="must contain 'src' and 'tgt' keys"):
                _add_single_campaign(campaign_file, False, "http://localhost:8001")

    def test_missing_tgt_key(self):
        """Test that items without 'tgt' key fail validation."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            with pytest.raises(ValueError, match="must contain 'src' and 'tgt' keys"):
                _add_single_campaign(campaign_file, False, "http://localhost:8001")

    def test_item_not_dict(self):
        """Test that non-dict items fail validation."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            with pytest.raises(ValueError, match="must be a dictionary"):
                _add_single_campaign(campaign_file, False, "http://localhost:8001")

    def test_document_not_list(self):
        """Test that non-list documents fail validation."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            with pytest.raises(ValueError, match="Items must be a list"):
                _add_single_campaign(campaign_file, False, "http://localhost:8001")

    def test_singlestream_missing_src(self):
        """Test that single-stream items without 'src' fail validation."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
                    "campaign_id": "test_ss_missing_src",
                    "info": {
                        "assignment": "single-stream",
                        "template": "basic",
                        "users": 2,
                    },
                    "data": [
                        [
                            {"tgt": {"A": "hola"}}  # Missing 'src'
                        ]
                    ]
                }, f)

            with pytest.raises(ValueError, match="must contain 'src' and 'tgt' keys"):
                _add_single_campaign(campaign_file, False, "http://localhost:8001")

    def test_extra_keys_allowed(self):
        """Test that extra keys beyond src/tgt are allowed."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            # Should not raise - extra keys are fine, use overwrite to avoid conflicts
            _add_single_campaign(campaign_file, True, "http://localhost:8001")

    def test_src_must_be_string(self):
        """Test that src must be a string."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            with pytest.raises(ValueError, match="'src' must be a string"):
                _add_single_campaign(campaign_file, False, "http://localhost:8001")



    def test_tgt_must_be_dict_only(self):
        """Test that tgt must be a dictionary (no longer accepts strings)."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            
            # Test with string - should now fail with helpful error
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)
            # Should fail with suggestion to use {"default": "..."}
            with pytest.raises(ValueError, match='For single translation, use \\{"default": "your_translation"\\}'):
                _add_single_campaign(campaign_file, True, "http://localhost:8001")
            
            # Test with invalid type - should fail
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            with pytest.raises(ValueError, match="'tgt' must be a dictionary mapping model names to translations"):
                _add_single_campaign(campaign_file, False, "http://localhost:8001")

    def test_tgt_elements_must_be_strings(self):
        """Test that all elements in tgt list must be strings (basic template)."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            with pytest.raises(ValueError, match="Translation for model 'B' must be a string"):
                _add_single_campaign(campaign_file, False, "http://localhost:8001")

    def test_basic_with_score_greaterthan_validation(self):
        """Test that basic template campaigns with score_greaterthan validation can be loaded."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_file = os.path.join(tmpdir, "campaign.json")
            with open(campaign_file, "w") as f:
                json.dump({
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
                }, f)

            # Should not raise - the score_greaterthan field is valid
            _add_single_campaign(campaign_file, True, "http://localhost:8001")
