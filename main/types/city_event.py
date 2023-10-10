import datetime
import enum
import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from ..utils.extraction_utils import flatten_list

logger = logging.getLogger(__name__)


class PaymentMode(enum.Enum):
    # Ticketed events like art shows, concerts, networking events and courses.
    ticket = "ticket"
    paid_membership = "paid_membership"  # Wellness, Subscription packages etc.
    appointment = "appointment"  # Appointments like Botox, Dental Cleaning, Cosmetic Surgery etc.
    in_premises = (
        "in_premises"  # In Premises like restaurants, bars, clubs, gyms etc.
    )


class CityEvent(BaseModel):
    name: str
    # More information summarizing the event, services offered, te
    description: str
    categories: list
    # TODO: Type might reflect ontology of events when we have it.
    addresses: Optional[List[str]] = Field(
        default=None,
    )
    # Like a museum, restaurant advertizing its services or new services.
    is_ongoing: bool = Field(
        default=False,
    )
    # The event's start date(which can be after the date time of the document) If the event is ongoing then start and end dates are moot.
    start_date: Optional[List[datetime.date]] = Field(
        default=None,
    )
    end_date: Optional[List[datetime.date]] = Field(
        default=None,
    )
    start_time: Optional[List[datetime.time]] = Field(
        default=None,
    )
    end_time: Optional[List[datetime.time]] = Field(
        default=None,
    )
    # means no payment, event is free and payment_mode will be None
    is_paid: bool = Field(
        default=False,
    )
    has_promotion: bool = Field(
        default=False,
    )
    promotion_details: Optional[str] = Field(
        default=None,
    )
    payment_mode: Optional[PaymentMode] = Field(
        default=None,
    )

    payment_details: Optional[str] = Field(
        default=None,
    )
    links: Optional[List[str]] = Field(default=None)

    def __str__(self):
        return ", ".join([k + "=" + str(v) for k, v in asdict(self).items()])

    def __post_init__(self):
        if not self.is_ongoing and self.start_date is None:
            logger.warn(
                "Event start date not mentioned but the event is not ongoing."
            )
        if self.is_paid and self.payment_mode is None:
            raise ValueError("Payment mode is required if the event is paid.")

        if self.addresses:
            self.addresses = flatten_list(self.addresses)
        if self.categories:
            self.categories = flatten_list(self.categories)
        if self.start_date:
            self.start_date = flatten_list(self.start_date)
        if self.end_date:
            self.end_date = flatten_list(self.end_date)
        if self.start_time:
            self.start_time = flatten_list(self.start_time)
        if self.end_time:
            self.end_time = flatten_list(self.end_time)
        if self.links:
            self.links = flatten_list(self.links)
