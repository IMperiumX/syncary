import json


class ConfigurationManager:
    _instance = None

    def __new__(cls, config_file="config.json"):
        if cls._instance is None:
            cls._instance = super(ConfigurationManager, cls).__new__(cls)
            cls._instance.config_file = config_file
            cls._instance.config_data = {}
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        """Loads configuration from the JSON file."""
        try:
            with open(self.config_file, "r") as f:
                self.config_data = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Configuration file not found: {self.config_file}")
            self.config_data = {}  # Default to empty config
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in {self.config_file}")
            # You might want to raise an exception here in a real application
            # to halt execution if the config is essential.
            self.config_data = {}

    def save_config(self):
        """Saves the current configuration to the JSON file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def get_config(self, key, default=None):
        """Retrieves a configuration value by key."""
        return self.config_data.get(key, default)

    def set_config(self, key, value):
        """Sets a configuration value."""
        self.config_data[key] = value
        self.save_config()

    def delete_config(self, key):
        """Deletes a configuration key if exists."""
        if key in self.config_data:
            del self.config_data[key]
            self.save_config()
