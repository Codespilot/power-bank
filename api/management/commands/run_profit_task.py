from datetime import date

from django.core.management.base import BaseCommand, CommandError

from api.profit_tasks import run_profit_allocation


class Command(BaseCommand):
    help = "Run the profit allocation task for the previous day or a specified date"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="run_date",
            help="Settlement date in YYYY-MM-DD format. Defaults to yesterday.",
        )

    def handle(self, *args, **options):
        run_date = None
        if options.get("run_date"):
            try:
                run_date = date.fromisoformat(options["run_date"])
            except ValueError as exc:
                raise CommandError("Invalid date format, expected YYYY-MM-DD") from exc

        result = run_profit_allocation(target_date=run_date)
        self.stdout.write(self.style.SUCCESS(f"Profit task completed: {result}"))
