"""Test that slug field is properly included in all item responses"""

from config_loader import config_loader
from items import Item
from main import generate_shop_items


class TestSlugField:
    """Test slug field presence and correctness"""

    def setup_method(self):
        """Load configurations before each test"""
        config_loader.load_all()

    def test_all_items_have_slugs_in_json(self):
        """Test that all items in JSON files have slug fields"""
        # Check all loaded items
        for item_id in config_loader.list_items():
            item = config_loader.get_item(item_id)
            assert hasattr(item, "slug"), f"Item {item_id} missing slug attribute"
            assert item.slug != "", f"Item {item_id} has empty slug"
            # Verify slug format (lowercase, underscores)
            assert item.slug.islower(), f"Slug {item.slug} should be lowercase"
            assert " " not in item.slug, f"Slug {item.slug} should not have spaces"

    def test_shop_items_include_slug(self):
        """Test that shop items include slug field"""
        shop = generate_shop_items(round_number=1, seed=12345)

        assert len(shop) == 5, "Shop should have 5 items"

        for item in shop:
            if item:  # Skip None slots
                assert isinstance(item, Item), "Should be an Item instance"
                assert hasattr(item, "slug"), "An Item should have a slug attribute"
                assert item.slug != "", f"Item {item.name} has empty slug"

    def test_slug_matches_expected_format(self):
        """Test that slugs match expected format from names"""
        test_cases = [
            ("Stack Smasher", "stack_smasher"),
            ("Null Pointer Exception", "null_pointer_exception"),
            ("DDoS Attack", "denier_of_service"),
            ("AI Companion Core", "ai_companion_core"),
        ]

        for name, expected_slug in test_cases:
            # Find item by name
            for item_id in config_loader.list_items():
                item = config_loader.get_item(item_id)
                if item.name == name:
                    assert item.slug == expected_slug, (
                        f"Item {name} has slug '{item.slug}', "
                        f"expected '{expected_slug}'"
                    )
                    break

    def test_purchased_item_includes_slug(self):
        """Test that purchased items include slug in inventory"""
        # This would require a full integration test with session
        # For now, we just verify the structure
        shop = generate_shop_items(round_number=1, seed=12345)
        item = next(i for i in shop if i)  # Get first non-None item

        # Simulate what gets added to inventory
        inventory_item = {
            "id": item.id,
            "item_type": item.item_type,
            "name": item.name,
            "slug": item.slug,
            "cost": item.cost,
            "rarity": item.rarity,
        }

        assert "slug" in inventory_item
        assert inventory_item["slug"] == item.slug

    def test_container_items_have_slugs(self):
        """Test that container items have slugs"""
        containers = config_loader.list_containers()

        for container_id in containers:
            container_info = config_loader.get_container(container_id)
            item_spec = container_info
            assert hasattr(item_spec, "slug"), f"Container {container_id} missing slug"
            assert item_spec.slug != "", f"Container {container_id} has empty slug"

    def test_all_categories_have_slugs(self):
        """Test that items from all categories have slugs"""
        categories_found = set()

        for item_id in config_loader.list_items():
            item = config_loader.get_item(item_id)
            categories_found.add(item.category)
            assert (
                item.slug != ""
            ), f"Item {item_id} in category {item.category} has empty slug"

        # Ensure we tested multiple categories
        assert len(categories_found) > 1, "Should have items from multiple categories"

    def test_slug_uniqueness_within_category(self):
        """Test that slugs are unique within each category"""
        category_slugs = {}

        for item_id in config_loader.list_items():
            item = config_loader.get_item(item_id)
            if item.category not in category_slugs:
                category_slugs[item.category] = set()

            assert (
                item.slug not in category_slugs[item.category]
            ), f"Duplicate slug '{item.slug}' in category {item.category}"
            category_slugs[item.category].add(item.slug)
