import os


def read_coding_lib(code_dir, file_dict):
    for file_name in os.listdir(code_dir):
        file_path = f"{code_dir}/{file_name}"
        if os.path.isdir(file_path):
            read_coding_lib(code_dir=file_path, file_dict=file_dict)
        else:
            with open(file_path, "r") as f:
                file_dict[file_name] = f.read()

