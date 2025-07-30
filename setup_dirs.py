import os

def create_directory_structure():
    base_dir = "storage"
    os.makedirs(base_dir, exist_ok=True)

    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    patterns_dir = os.path.join(base_dir, "patterns")
    os.makedirs(patterns_dir, exist_ok=True)

    for i in range(256):
        folder_name = f"{i:02x}"  
        os.makedirs(os.path.join(patterns_dir, folder_name), exist_ok=True)

    print("Excellent!")

if __name__ == "__main__":
    create_directory_structure()