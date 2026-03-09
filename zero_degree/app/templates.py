from jinja2 import Environment, FileSystemLoader, ChoiceLoader
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone

def timesince(value: datetime) -> str:
    if value is None:
        return ""

    now = datetime.now(timezone.utc)  # aware datetime
    if value.tzinfo is None:  # if DB datetime is naive
        value = value.replace(tzinfo=timezone.utc)

    diff = now - value
    seconds = diff.total_seconds()

    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60
    days = diff.days

    if diff.total_seconds() < 0:
        return "just now"
    elif seconds < 60:
        unit = "sec" if int(seconds) == 1 else "secs"
        return f"{int(seconds)} {unit} ago"
    elif minutes < 60:
        unit = "min" if int(minutes) == 1 else "mins"
        return f"{int(minutes)} {unit} ago"
    elif hours < 24:
        unit = "hr" if int(hours) == 1 else "hrs"
        return f"{int(hours)} {unit} ago"
    else:
        unit = "day" if int(days) == 1 else "days"
        return f"{int(days)} {unit} ago"



def get_templates(directory: str, macros_dir: str | None = None) -> Jinja2Templates:
    loaders = [
        FileSystemLoader(directory),
        FileSystemLoader(macros_dir) if macros_dir else None,
    ]

    env = Environment(loader=ChoiceLoader(loaders), autoescape=True)

    # Inject user automatically
    def current_user(request):
        return getattr(request.state, "user", None)

    # Expose helpers, not results
    env.globals["current_user"] = current_user
    env.globals["now"] = datetime.now 

    # Filters
    env.filters["timesince"] = timesince

    templates = Jinja2Templates(directory=directory)
    templates.env = env
    return templates
