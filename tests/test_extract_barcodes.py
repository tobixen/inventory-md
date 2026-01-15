"""Tests for barcode extraction and ISBN/EAN lookup functionality."""
import pytest
from unittest.mock import patch, MagicMock

# Import the module under test
import sys
sys.path.insert(0, str(__file__).rsplit('/tests/', 1)[0] + '/scripts')
from extract_barcodes import (
    normalize_isbn,
    validate_isbn10_checksum,
    validate_isbn13_checksum,
    validate_ean_checksum,
    is_isbn,
    isbn10_to_isbn13,
    is_lookupable,
    is_ean,
    lookup_code,
    format_for_inventory,
)


class TestNormalizeIsbn:
    """Tests for ISBN normalization."""

    def test_removes_hyphens(self):
        assert normalize_isbn("978-0-13-468599-1") == "9780134685991"

    def test_removes_spaces(self):
        assert normalize_isbn("978 0 13 468599 1") == "9780134685991"

    def test_removes_mixed_separators(self):
        assert normalize_isbn("978-0 13-468599 1") == "9780134685991"

    def test_preserves_digits(self):
        assert normalize_isbn("9780134685991") == "9780134685991"

    def test_preserves_x_checksum(self):
        assert normalize_isbn("0-306-40615-X") == "030640615X"


class TestValidateIsbn10Checksum:
    """Tests for ISBN-10 checksum validation."""

    def test_valid_isbn10(self):
        assert validate_isbn10_checksum("0306406152") is True

    def test_valid_isbn10_with_x(self):
        # 155860832X is a valid ISBN-10 (The C Programming Language)
        assert validate_isbn10_checksum("155860832X") is True

    def test_valid_isbn10_lowercase_x(self):
        # X can be lowercase
        assert validate_isbn10_checksum("155860832x") is True

    def test_invalid_isbn10_wrong_checksum(self):
        assert validate_isbn10_checksum("0306406151") is False

    def test_invalid_isbn10_wrong_length(self):
        assert validate_isbn10_checksum("03064061") is False
        assert validate_isbn10_checksum("03064061521") is False

    def test_invalid_isbn10_non_digits(self):
        assert validate_isbn10_checksum("030640615A") is False


class TestValidateIsbn13Checksum:
    """Tests for ISBN-13 checksum validation."""

    def test_valid_isbn13_978(self):
        assert validate_isbn13_checksum("9780134685991") is True

    def test_valid_isbn13_979(self):
        # 979 prefix ISBNs exist (French publishers, etc.)
        assert validate_isbn13_checksum("9791032305690") is True

    def test_invalid_isbn13_wrong_checksum(self):
        assert validate_isbn13_checksum("9780134685992") is False

    def test_invalid_isbn13_not_978_979(self):
        # Valid EAN-13 but not an ISBN (doesn't start with 978/979)
        assert validate_isbn13_checksum("5901234123457") is False

    def test_invalid_isbn13_wrong_length(self):
        assert validate_isbn13_checksum("978013468599") is False
        assert validate_isbn13_checksum("97801346859912") is False


class TestValidateEanChecksum:
    """Tests for EAN/UPC checksum validation."""

    def test_valid_ean13(self):
        assert validate_ean_checksum("5901234123457") is True

    def test_valid_ean8(self):
        assert validate_ean_checksum("96385074") is True

    def test_valid_upc_a(self):
        assert validate_ean_checksum("012345678905") is True

    def test_invalid_ean13(self):
        assert validate_ean_checksum("5901234123458") is False

    def test_invalid_length(self):
        assert validate_ean_checksum("12345") is False
        assert validate_ean_checksum("12345678901234") is False

    def test_non_digits(self):
        assert validate_ean_checksum("590123412345X") is False


class TestIsIsbn:
    """Tests for ISBN detection."""

    def test_isbn13_with_978(self):
        assert is_isbn("9780134685991") is True

    def test_isbn13_with_979(self):
        assert is_isbn("9791032305690") is True

    def test_isbn13_with_hyphens(self):
        assert is_isbn("978-0-13-468599-1") is True

    def test_isbn10(self):
        assert is_isbn("0306406152") is True

    def test_isbn10_with_x(self):
        assert is_isbn("155860832X") is True

    def test_isbn10_with_hyphens(self):
        assert is_isbn("0-306-40615-2") is True

    def test_regular_ean_not_isbn(self):
        # Valid EAN-13 but not an ISBN
        assert is_isbn("5901234123457") is False

    def test_invalid_checksum_not_isbn(self):
        assert is_isbn("9780134685992") is False

    def test_short_number_not_isbn(self):
        assert is_isbn("12345") is False


class TestIsbn10ToIsbn13:
    """Tests for ISBN-10 to ISBN-13 conversion."""

    def test_converts_correctly(self):
        # 0306406152 should become 9780306406157
        result = isbn10_to_isbn13("0306406152")
        assert result == "9780306406157"
        assert validate_isbn13_checksum(result) is True

    def test_handles_hyphens(self):
        result = isbn10_to_isbn13("0-306-40615-2")
        assert result == "9780306406157"

    def test_returns_input_if_wrong_length(self):
        assert isbn10_to_isbn13("12345") == "12345"


class TestIsLookupable:
    """Tests for barcode lookupability detection."""

    def test_isbn13_detected(self):
        can_lookup, code_type = is_lookupable("EAN13", "9780134685991")
        assert can_lookup is True
        assert code_type == "isbn"

    def test_isbn10_detected(self):
        can_lookup, code_type = is_lookupable("CODE128", "0306406152")
        assert can_lookup is True
        assert code_type == "isbn"

    def test_ean13_detected(self):
        can_lookup, code_type = is_lookupable("EAN13", "5901234123457")
        assert can_lookup is True
        assert code_type == "ean"

    def test_ean8_detected(self):
        can_lookup, code_type = is_lookupable("EAN8", "96385074")
        assert can_lookup is True
        assert code_type == "ean"

    def test_upca_detected(self):
        can_lookup, code_type = is_lookupable("UPCA", "012345678905")
        assert can_lookup is True
        assert code_type == "ean"

    def test_qrcode_not_lookupable(self):
        can_lookup, code_type = is_lookupable("QRCODE", "https://example.com")
        assert can_lookup is False
        assert code_type == ""


class TestIsEan:
    """Tests for is_ean (legacy function)."""

    def test_returns_true_for_isbn(self):
        # is_ean returns True for ISBNs too (they can be looked up)
        assert is_ean("EAN13", "9780134685991") is True

    def test_returns_true_for_ean(self):
        assert is_ean("EAN13", "5901234123457") is True

    def test_returns_false_for_qrcode(self):
        assert is_ean("QRCODE", "https://example.com") is False


class TestLookupCode:
    """Tests for code lookup routing."""

    def test_isbn_routes_to_openlibrary(self):
        """Test that ISBNs are routed to Open Library, not OpenFoodFacts."""
        with patch('extract_barcodes.lookup_openlibrary') as mock_ol, \
             patch('extract_barcodes.lookup_ean_online') as mock_ean:
            mock_ol.return_value = {'name': 'Test Book', 'type': 'book'}

            product, cached = lookup_code("9780134685991", {}, use_cache=False)

            mock_ol.assert_called_once_with("9780134685991")
            mock_ean.assert_not_called()
            assert product['type'] == 'book'

    def test_ean_routes_to_openfoodfacts(self):
        """Test that EANs are routed to OpenFoodFacts."""
        with patch('extract_barcodes.lookup_openlibrary') as mock_ol, \
             patch('extract_barcodes.lookup_ean_online') as mock_ean:
            mock_ean.return_value = {'name': 'Test Product', 'source': 'openfoodfacts'}

            product, cached = lookup_code("5901234123457", {}, use_cache=False)

            mock_ean.assert_called_once_with("5901234123457")
            mock_ol.assert_not_called()

    def test_cache_hit_returns_cached(self):
        """Test that cache hits return cached data without API call."""
        cache = {"9780134685991": {'name': 'Cached Book', 'type': 'book'}}

        with patch('extract_barcodes.lookup_openlibrary') as mock_ol:
            product, cached = lookup_code("9780134685991", cache, use_cache=True)

            mock_ol.assert_not_called()
            assert cached is True
            assert product['name'] == 'Cached Book'

    def test_cache_none_means_not_found(self):
        """Test that None in cache means 'looked up but not found'."""
        cache = {"5901234123457": None}

        with patch('extract_barcodes.lookup_ean_online') as mock_ean:
            product, cached = lookup_code("5901234123457", cache, use_cache=True)

            mock_ean.assert_not_called()
            assert cached is True
            assert product is None


class TestFormatForInventory:
    """Tests for inventory format output."""

    def test_book_format(self):
        barcode = {'type': 'EAN13', 'data': '9780134685991'}
        product = {
            'type': 'book',
            'isbn': '9780134685991',
            'name': 'Test Book',
            'author': 'John Doe',
            'publisher': 'Publisher Inc',
            'publish_date': '2020',
        }

        result = format_for_inventory(barcode, product)

        assert result.startswith('* tag:book ISBN:9780134685991')
        assert '"Test Book" by John Doe' in result
        assert '(Publisher Inc, 2020)' in result

    def test_book_format_no_author(self):
        barcode = {'type': 'EAN13', 'data': '9780134685991'}
        product = {
            'type': 'book',
            'isbn': '9780134685991',
            'name': 'Test Book',
            'author': None,
            'publisher': 'Publisher Inc',
        }

        result = format_for_inventory(barcode, product)

        assert '"Test Book"' in result
        assert 'by' not in result

    def test_product_format(self):
        barcode = {'type': 'EAN13', 'data': '5901234123457'}
        product = {
            'name': 'Test Product',
            'brand': 'Brand X',
            'quantity': '500g',
        }

        result = format_for_inventory(barcode, product)

        assert result == '* EAN:5901234123457 Brand X Test Product (500g)'

    def test_unknown_isbn_format(self):
        barcode = {'type': 'EAN13', 'data': '9780134685991'}
        product = None

        result = format_for_inventory(barcode, product)

        assert result == '* tag:book ISBN:9780134685991 (unknown book)'

    def test_unknown_ean_format(self):
        barcode = {'type': 'EAN13', 'data': '5901234123457'}
        product = None

        result = format_for_inventory(barcode, product)

        assert '* EAN:5901234123457 (unknown product' in result


class TestRealWorldIsbns:
    """Tests with real-world ISBN examples."""

    @pytest.mark.parametrize("isbn,expected", [
        ("9781846461828", True),   # Ladybird book
        ("9785222394137", True),   # Russian book
        ("978-1-78243-517-4", True),  # With hyphens
        ("0451526538", True),      # ISBN-10: 1984 by Orwell
        ("0-545-01022-5", True),   # ISBN-10 with hyphens: Harry Potter
    ])
    def test_real_isbns_detected(self, isbn, expected):
        assert is_isbn(isbn) is expected

    @pytest.mark.parametrize("ean", [
        "7622210678546",  # Freia chocolate
        "5902062007025",  # Welding electrodes
        "4008153752353",  # UNITEC product
    ])
    def test_real_eans_not_isbns(self, ean):
        assert is_isbn(ean) is False
        assert validate_ean_checksum(ean) is True
