import datetime
import enum
import logging
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from main.utils.extraction_utils import flatten_list

logger = logging.getLogger(__name__)


class PaymentMode(enum.Enum):
    # Ticketed events like art shows, concerts, networking events and courses.
    ticket = 1
    paid_membership = 2  # Wellness, Subscription packages etc.
    appointment = (
        3  # Appointments like Botox, Dental Cleaning, Cosmetic Surgery etc.
    )
    in_premises = 4  # In Premises like restaurants, bars, clubs, gyms etc.


@dataclass
class Event:
    name: str
    # More information summarizing the event, services offered, te
    description: str
    categories: list
    # TODO: Type might reflect ontology of events when we have it.
    addresses: Optional[List[str]] = field(
        default=None,
    )
    # Like a museum, restaurant advertizing its services or new services.
    is_ongoing: bool = field(
        default=False,
    )
    # The event's start date(which can be after the date time of the document) If the event is ongoing then start and end dates are moot.
    start_date: Optional[List[datetime.date]] = field(
        default=None,
    )
    end_date: Optional[List[datetime.date]] = field(
        default=None,
    )
    start_time: Optional[List[datetime.time]] = field(
        default=None,
    )
    end_time: Optional[List[datetime.time]] = field(
        default=None,
    )
    # means no payment, event is free and payment_mode will be None
    is_paid: bool = field(
        default=False,
    )
    has_promotion: bool = field(
        default=False,
    )
    promotion_details: Optional[str] = field(
        default=None,
    )
    payment_mode: Optional[PaymentMode] = field(
        default=None,
    )

    payment_details: Optional[str] = field(
        default=None,
    )
    links: Optional[List[str]] = field(default=None)

    def __str__(self):
        return ', '.join([k+'='+str(v) for k, v in asdict(self).items()])

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


# Maybe there is a better way to do this
def create_event(
    name: str,
    description: str,
    categories: list,
    addresses: Optional[List[str]] = None,
    is_ongoing: bool = False,
    start_date: Optional[List[datetime.date]] = None,
    end_date: Optional[List[datetime.date]] = None,
    start_time: Optional[List[datetime.time]] = None,
    end_time: Optional[List[datetime.time]] = None,
    is_paid: bool = False,
    has_promotion: bool = False,
    promotion_details: Optional[str] = None,
    payment_mode: Optional[PaymentMode] = None,
    payment_details: Optional[str] = None,
    links: Optional[List[str]] = None,

) -> Event:
    # Write a function that accepts an event  string and for each field in the Event class fills the fields with appropriate values extracted
    # from the text and returns the Event object.
    #   Call teh OpenAI GPT-3 API to fill each field
    #   Parsing Rules: If  GPT determines event is ongoig then the date fields are empty and only payment fields might be fillable.
    #   If GPT determines that a field is not applicable it will set the field to None.
    #   At the end use the click library to ask the user if the fields are correct and if the user determines some fields need to be corrected then the user is asked to manually input the field.
    #   All interactions for each event are logged in a json array along with corrective action taken by the user.
    #   The json array is then saved to a file.
    return Event(
        name=name,
        description=description,
        categories=categories,
        addresses=addresses,
        is_ongoing=is_ongoing,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        is_paid=is_paid,
        has_promotion=has_promotion,
        promotion_details=promotion_details,
        payment_mode=payment_mode,
        payment_details=payment_details,
        links=links,
    )


def sort_alphabet_list_reverse(lst: List[str]) -> List[str]:
    return sorted(lst, reverse=True)
