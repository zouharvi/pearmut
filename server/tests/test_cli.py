"""Tests for CLI functionality."""

import os
import random
import tempfile

import pytest


class TestOverwriteData:
    """Tests for overwrite functionality."""

    def test_overwrite_removes_output_file(self):
        """Test that overwrite removes existing output file (annotations)."""
        from pearmut.cli import ROOT, _add_single_campaign
        from pearmut.utils import load_progress_data, save_progress_data

        campaign_id = "test_overwrite_campaign"
        
        # Clean up any leftover data from previous test runs
        progress_data = load_progress_data()
        if campaign_id in progress_data:
            del progress_data[campaign_id]
            save_progress_data(progress_data)
        task_file = f"{ROOT}/data/campaigns/{campaign_id}.json"
        if os.path.exists(task_file):
            os.remove(task_file)
        output_file = f"{ROOT}/data/annotations/{campaign_id}.jsonl"
        if os.path.exists(output_file):
            os.remove(output_file)
        
        # Add campaign for the first time
        _add_single_campaign({
            "campaign_id": campaign_id,
            "info": {
                "assignment": "task-based",
                "protocol": "ESA",
            },
            "data": [[[{"src": "hello", "tgt": {"A": "world"}}]]]
        }, False, "http://localhost:8001")
        
        # Create a mock output file with annotations
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            f.write('{"annotation": "test data"}\n')
        
        # Verify output file exists
        assert os.path.exists(output_file)
        
        # Add campaign again with overwrite (using fresh data)
        _add_single_campaign({
            "campaign_id": campaign_id,
            "info": {
                "assignment": "task-based",
                "protocol": "ESA",
            },
            "data": [[[{"src": "hello", "tgt": {"A": "world"}}]]]
        }, True, "http://localhost:8001")
        
        # Verify output file was removed
        assert not os.path.exists(output_file)
        
        # Clean up
        progress_data = load_progress_data()
        if campaign_id in progress_data:
            del progress_data[campaign_id]
            save_progress_data(progress_data)
        if os.path.exists(task_file):
            os.remove(task_file)


class TestAssetsValidation:
    """Tests for assets validation in add command."""

    def test_assets_must_be_dict(self):
        """Test that assets must be a dictionary."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test assets directory
            assets_dir = os.path.join(tmpdir, "videos")
            os.makedirs(assets_dir)

            campaign_data = {
                "campaign_id": "test_campaign",
                "info": {
                    "assignment": "task-based",
                    "template": "basic",
                    "assets": assets_dir,
                },
                "data": [[[{"src": "a", "tgt": {"A": "b"}}]]]
            }

            with pytest.raises(ValueError, match="Assets must be a dictionary"):
                _add_single_campaign(campaign_data, False, "http://localhost:8001")

    def test_assets_requires_source_key(self):
        """Test that assets must have source key."""
        from pearmut.cli import _add_single_campaign

        campaign_data = {
            "campaign_id": "test_campaign",
            "info": {
                "assignment": "task-based",
                "template": "basic",
                "assets": {"destination": "assets/my_videos"},
            },
            "data": [[[{"src": "a", "tgt": {"A": "b"}}]]]
        }

        with pytest.raises(ValueError, match="must contain 'source' and 'destination' keys"):
            _add_single_campaign(campaign_data, False, "http://localhost:8001")

    def test_assets_requires_destination_key(self):
        """Test that assets must have destination key."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            assets_dir = os.path.join(tmpdir, "videos")
            os.makedirs(assets_dir)

            campaign_data = {
                "campaign_id": "test_campaign",
                "info": {
                    "assignment": "task-based",
                    "template": "basic",
                    "assets": {"source": assets_dir},
                },
                "data": [[[{"src": "a", "tgt": {"A": "b"}}]]]
            }

            with pytest.raises(ValueError, match="must contain 'source' and 'destination' keys"):
                _add_single_campaign(campaign_data, False, "http://localhost:8001")

    def test_assets_destination_must_start_with_assets(self):
        """Test that assets destination must start with 'assets/'."""
        from pearmut.cli import _add_single_campaign

        with tempfile.TemporaryDirectory() as tmpdir:
            assets_dir = os.path.join(tmpdir, "videos")
            os.makedirs(assets_dir)

            campaign_data = {
                "campaign_id": "test_campaign",
                "info": {
                    "assignment": "task-based",
                    "template": "basic",
                    "assets": {
                        "source": assets_dir,
                        "destination": "my_videos"
                    },
                },
                "data": [[[{"src": "a", "tgt": {"A": "b"}}]]]
            }

            with pytest.raises(ValueError, match="must start with 'assets/'"):
                _add_single_campaign(campaign_data, False, "http://localhost:8001")

    def test_assets_source_must_exist(self):
        """Test that assets source directory must exist."""
        from pearmut.cli import ROOT, _add_single_campaign

        # Create data directory
        data_dir = f"{ROOT}/data/campaigns"
        os.makedirs(data_dir, exist_ok=True)

        campaign_data = {
            "campaign_id": "test_campaign",
            "info": {
                "assignment": "task-based",
                "template": "basic",
                "assets": {
                    "source": "/nonexistent/path",
                    "destination": "assets/my_videos"
                },
            },
            "data": [[[{"src": "a", "tgt": {"A": "b"}}]]]
        }

        with pytest.raises(ValueError, match="must be an existing directory"):
            _add_single_campaign(campaign_data, False, "http://localhost:8001")


class TestShuffleData:
    """Tests for shuffle functionality in campaigns."""

    def test_shuffle_reorders_models(self):
        """Test that shuffle reorders model names in tgt dictionary."""
        from pearmut.cli import _shuffle_campaign_data
        
        rng = random.Random(42)
        campaign_data = {
            "info": {"assignment": "task-based"},
            "data": {
                "user1": [
                    [  # Document 1
                        {"src": "hello", "tgt": {"model_A": "hola", "model_B": "bonjour", "model_C": "ciao"}},
                        {"src": "world", "tgt": {"model_A": "mundo", "model_B": "monde", "model_C": "mondo"}}
                    ]
                ]
            }
        }
        
        # Get original order
        original_order = list(campaign_data["data"]["user1"][0][0]["tgt"].keys())
        
        # Shuffle
        _shuffle_campaign_data(campaign_data, rng)
        
        # Get new order
        new_order = list(campaign_data["data"]["user1"][0][0]["tgt"].keys())
        
        # Order should be different (with seed 42 and 3 models, it will be shuffled)
        assert new_order != original_order
        
        # All models should still be present
        assert set(new_order) == set(original_order)
        
        # Both items in the document should have the same order
        doc = campaign_data["data"]["user1"][0]
        assert list(doc[0]["tgt"].keys()) == list(doc[1]["tgt"].keys())

    def test_shuffle_refuses_different_models_in_document(self):
        """Test that shuffle raises an error when items have different model outputs."""
        from pearmut.cli import _shuffle_campaign_data
        
        rng = random.Random(42)
        campaign_data = {
            "info": {"assignment": "task-based"},
            "data": {
                "user1": [
                    [  # Document with different models per item
                        {"src": "hello", "tgt": {"model_A": "hola", "model_B": "bonjour"}},
                        {"src": "world", "tgt": {"model_A": "mundo", "model_C": "monde"}}  # Different model!
                    ]
                ]
            }
        }
        
        # Should raise ValueError with helpful message
        with pytest.raises(ValueError, match="Document contains items with different model outputs"):
            _shuffle_campaign_data(campaign_data, rng)
        
        # Error message should mention setting shuffle to false
        with pytest.raises(ValueError, match="set 'shuffle': false"):
            _shuffle_campaign_data(campaign_data, rng)

    def test_shuffle_refuses_different_models_single_stream(self):
        """Test that shuffle raises an error for single-stream with different models."""
        from pearmut.cli import _shuffle_campaign_data
        
        rng = random.Random(42)
        campaign_data = {
            "info": {"assignment": "single-stream"},
            "data": [
                [  # Document with different models per item
                    {"src": "hello", "tgt": {"model_A": "hola", "model_B": "bonjour"}},
                    {"src": "world", "tgt": {"model_A": "mundo", "model_C": "monde"}}
                ]
            ]
        }
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Document contains items with different model outputs"):
            _shuffle_campaign_data(campaign_data, rng)

    def test_add_campaign_with_different_models_and_shuffle_disabled(self):
        """Test that campaigns with different models can be added if shuffle is disabled."""
        from pearmut.cli import _add_single_campaign
        
        campaign_data = {
            "campaign_id": "test_mixed_models",
            "info": {
                "assignment": "task-based",
                "shuffle": False  # Explicitly disable shuffle
            },
            "data": [
                [  # Task with document containing different models
                    [
                        {"src": "hello", "tgt": {"model_A": "hola", "model_B": "bonjour"}},
                        {"src": "world", "tgt": {"model_A": "mundo", "model_C": "monde"}}
                    ]
                ]
            ]
        }
        
        # Should not raise an error
        _add_single_campaign(campaign_data, True, "http://localhost:8001")

    def test_add_campaign_with_different_models_and_shuffle_enabled(self):
        """Test that campaigns with different models fail when shuffle is enabled."""
        from pearmut.cli import _add_single_campaign
        
        campaign_data = {
            "campaign_id": "test_mixed_models_fail",
            "info": {
                "assignment": "task-based",
                "shuffle": True  # Shuffle enabled (or omitted, defaults to True)
            },
            "data": [
                [  # Task with document containing different models
                    [
                        {"src": "hello", "tgt": {"model_A": "hola", "model_B": "bonjour"}},
                        {"src": "world", "tgt": {"model_A": "mundo", "model_C": "monde"}}
                    ]
                ]
            ]
        }
        
        # Should raise ValueError with helpful message
        with pytest.raises(ValueError, match="Document contains items with different model outputs"):
            _add_single_campaign(campaign_data, True, "http://localhost:8001")
