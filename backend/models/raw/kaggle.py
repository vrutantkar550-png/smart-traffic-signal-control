import kagglehub

# Download latest version
path = kagglehub.dataset_download("bratjay/ua-detrac-orig")

print("Path to dataset files:", path)
