"""
Test script to verify ALLOWED_ORIGINS parsing works with different formats.
"""
import os
import sys

# Test different ALLOWED_ORIGINS formats
test_cases = [
    ('["http://localhost:3000"]', "JSON array string (single)"),
    ('["http://localhost:3000","http://localhost:3001"]', "JSON array string (multiple)"),
    ('http://localhost:3000', "Single value"),
    ('http://localhost:3000,http://localhost:3001', "Comma-separated"),
    ('http://localhost:3000, http://localhost:3001', "Comma-separated with spaces"),
]

print("Testing ALLOWED_ORIGINS parsing...")
print("=" * 60)

for value, description in test_cases:
    # Set environment variable
    os.environ['ALLOWED_ORIGINS'] = value

    # Remove cached settings
    if 'app.core.config' in sys.modules:
        del sys.modules['app.core.config']

    try:
        from app.core.config import Settings
        settings = Settings()

        print(f"\n✓ {description}")
        print(f"  Input:  {value!r}")
        print(f"  Output: {settings.ALLOWED_ORIGINS}")
        print(f"  Type:   {type(settings.ALLOWED_ORIGINS)}")

        # Verify it's a list
        assert isinstance(settings.ALLOWED_ORIGINS, list), "Must be a list"
        assert all(isinstance(x, str) for x in settings.ALLOWED_ORIGINS), "All items must be strings"

    except Exception as e:
        print(f"\n✗ {description}")
        print(f"  Input:  {value!r}")
        print(f"  Error:  {e}")
        sys.exit(1)

print("\n" + "=" * 60)
print("✓ All test cases passed!")
