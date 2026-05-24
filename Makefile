.PHONY: install seed run demo clean

# Install dependencies
install:
	uv sync

# Create test users in the database
seed:
	uv run python seed.py

# Start all 3 services + gateway (single terminal, Ctrl+C to stop)
run:
	uv run python run.py

# Run the all-in-one demo (no separate servers needed)
demo:
	@rm -f users.db
	uv run python demo.py

# Remove generated files
clean:
	@rm -f users.db
	@echo "Cleaned."