import random
import re
import time
from dataclasses import dataclass
from typing import Protocol

from app.models import PaymentMethod


@dataclass(frozen=True)
class GatewayResult:
    succeeded: bool
    failure_reason: str | None = None
    card_brand: str | None = None


class PaymentProvider(Protocol):
    def process(
        self,
        method: PaymentMethod,
        *,
        card_number: str | None = None,
        expiry: str | None = None,
        upi_id: str | None = None,
    ) -> GatewayResult: ...


def luhn_valid(card_number: str) -> bool:
    if not re.fullmatch(r"[0-9 -]+", card_number):
        return False
    digits = re.sub(r"[ -]", "", card_number)
    if not 12 <= len(digits) <= 19:
        return False
    checksum = 0
    for position, character in enumerate(reversed(digits)):
        digit = int(character)
        if position % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _card_brand(card_number: str) -> str:
    digits = re.sub(r"\D", "", card_number)
    if digits.startswith("4"):
        return "Visa"
    if digits[:2] in {str(number) for number in range(51, 56)} or digits[:4] in {"2221", "2720"}:
        return "Mastercard"
    if digits.startswith(("34", "37")):
        return "American Express"
    return "Card"


class MockGateway:
    def __init__(self, delay_range: tuple[float, float] = (1.0, 2.0)):
        self.delay_range = delay_range

    def process(
        self,
        method: PaymentMethod,
        *,
        card_number: str | None = None,
        expiry: str | None = None,
        upi_id: str | None = None,
    ) -> GatewayResult:
        time.sleep(random.uniform(*self.delay_range))

        if method == PaymentMethod.CARD:
            digits = re.sub(r"\D", "", card_number or "")
            brand = _card_brand(digits) if digits else None
            if digits == "4000000000000002":
                return GatewayResult(False, "Declined: insufficient funds", brand)
            if digits == "4000000000000069":
                return GatewayResult(False, "Card expired", brand)
            if digits == "4000000000000119":
                return GatewayResult(False, "Processing error; please try again", brand)
            if not luhn_valid(digits):
                return GatewayResult(False, "Invalid card number (Luhn check failed)", brand)
            if expiry and self._is_expired(expiry):
                return GatewayResult(False, "Card expired", brand)
            if digits != "4111111111111111":
                return GatewayResult(False, "Card declined by mock gateway", brand)
            return GatewayResult(True, card_brand=brand)

        if method == PaymentMethod.ONLINE:
            if upi_id == "success@test" or upi_id is None:
                return GatewayResult(True)
            if upi_id == "fail@test":
                return GatewayResult(False, "UPI payment failed in test mode")
            return GatewayResult(False, "Unsupported UPI test ID; use success@test or fail@test")

        return GatewayResult(False, "COD does not use gateway processing")

    @staticmethod
    def _is_expired(expiry: str) -> bool:
        month, year = expiry.split("/")
        from datetime import datetime

        now = datetime.now()
        return (2000 + int(year), int(month)) < (now.year, now.month)


mock_gateway = MockGateway()


def get_payment_provider() -> PaymentProvider:
    return mock_gateway
