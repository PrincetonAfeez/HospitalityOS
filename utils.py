import os

class PathManager:
    """
    Commit 1: Centralized path management to prevent 
    'File Not Found' errors across different OS environments.
    """
    # Get the absolute path of the directory containing this file
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Define the 'data' directory for all CSVs and JSONs
    DATA_DIR = os.path.join(BASE_DIR, "data")

    @classmethod
    def get_path(cls, filename):
        """
        Returns the absolute path for a data file and 
        ensures the data directory exists.
        """
        if not os.path.exists(cls.DATA_DIR):
            os.makedirs(cls.DATA_DIR)
        return os.path.join(cls.DATA_DIR, filename)