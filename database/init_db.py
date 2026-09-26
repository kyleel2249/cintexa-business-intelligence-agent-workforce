"""Initialise database schema (development / test helper)."""

from database.session import init_db, get_database_url


def main() -> None:
    url = get_database_url()
    print(f"Initialising database: {url}")
    init_db(url)
    print("Schema created.")


if __name__ == "__main__":
    main()
