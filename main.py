import os
import evadb
import subprocess
import pandas as pd
from helper import read_coding_lib

DEFAULT_PROMPT_PATH = "default_prompts/password_generator/prompt"
os.environ["OPENAI_API_KEY"] = \
    os.environ.get("OPENAI_API_KEY", "sk-111111111111111111111111111111111111")
os.environ["OPENAI_KEY"] = os.environ["OPENAI_API_KEY"]


def receive_prompt():
    # we will return the prompt str
    prompt = ""

    print("Welcome to EvaDB, you can create any coding project on your local. "
          "\nYou only need to supply a prompt describing your coding project"
          " and an OpenAI API key.")
    from_file = str(
        input(
            "Do you have a prompt located in a file "
            "('yes' for local file/ 'no' for taking input now)"
        )
    ).lower() in ["y", "yes"]

    if from_file:
        prompt_path = str(
            input(
                "Enter the location of the local prompt file video "
                "(press Enter to use our default prompt): "
            )
        )
        if prompt_path == "":
            prompt_path = DEFAULT_PROMPT_PATH

        with open(prompt_path, "rb") as f:
            prompt = f.read()

    else:
        prompt = str(
            input(
                "Enter the prompt describing your code. "
                "(press Enter to use our default prompt): "
            )
        )

        if prompt == "":
            with open(DEFAULT_PROMPT_PATH, "rb") as f:
                prompt = f.read()

    # get OpenAI key if needed
    try:
        os.environ["OPENAI_API_KEY"]
    except KeyError:
        api_key = str(input("🔑 Enter your OpenAI key: "))
        os.environ["OPENAI_API_KEY"] = api_key

    return prompt


def summarize_project(cursor):
    generate_summary_rel = cursor.table("Summary").select(
        "ChatGPT('summarize in detail', summary)"
    )
    responses = generate_summary_rel.df()["chatgpt.response"]
    summary = " ".join(responses)

    print(summary)


def generate_code(prompt, cursor):
    # we will store the codes inside a temp folder
    project_path = f"{os.getcwd()}/temp"
    if not os.path.exists(project_path):
        os.makedirs(project_path)
        file_index = 1
    else:
        # temp exits get the file_index
        file_indices = [int(file_name.split("-")[1])
                        for file_name in os.listdir(project_path)]
        file_index = sorted(file_indices)[-1] + 1

    # write the prompt to a file in the temp directory
    project_path = f"{project_path}/project-{file_index}"
    os.makedirs(project_path)
    prompt_path = f"{project_path}/prompt"
    with open(prompt_path, "w") as f:
        f.write(prompt)

    # generate the code by calling gpt-engineer
    print(f"Creating the project-{file_index} inside {project_path}")
    print("-*-*" * 30)
    command = ["gpt-engineer", project_path]
    proc = subprocess.run(command, text=True)

    # index the generated code into EvaDB
    file_index = 2
    project_path = f"{project_path}/project-{file_index}"
    index_code(project_path, cursor)

    return file_index


def index_code(project_path, cursor):
    project_id = int(os.path.basename(project_path).split("-")[1])
    workspace_path = f"{project_path}/workspace"
    code_contents = {}
    read_coding_lib(code_dir=workspace_path, file_dict=code_contents)
    data = {
        "project_id": [project_id] * len(code_contents),
        "file_names": list(code_contents.keys()),
        "file_path": [project_path] * len(code_contents)
    }
    data_df = pd.DataFrame(data=data)
    summary_df = pd.DataFrame([{"project_id": [project_id],
                                "summary": code_contents["all_output.txt"]}])

    cursor.query(
        """CREATE TABLE IF NOT EXISTS Summary (project_id INTEGER, summary TEXT(1000));"""
    ).execute()
    summary_path = f"{project_path}/summary.csv"
    summary_df.to_csv(summary_path)
    cursor.load(summary_path, "Summary", "csv").execute()

    cursor.query(
        """CREATE TABLE IF NOT EXISTS Codes (project_id INTEGER, file_names TEXT(20), file_path TEXT(100));"""
    ).execute()
    data_path = f"{project_path}/data.csv"
    data_df.to_csv(data_path)
    cursor.load(data_path, "Codes", "csv").execute()



def execute_code(project_id):
    project_path = f"{os.getcwd()}/temp/project-{project_id}"

    print(f"Executing the project-{project_id} inside {project_path}")
    print("-*-*" * 30)
    os.chdir(f"temp/project-{project_id}/workspace/")
    command = ["chmod", "+x", "run.sh"]
    proc = subprocess.run(command, text=True)

    command = [f"./run.sh"]
    proc = subprocess.run(command, text=True)


def run():
    cursor = evadb.connect().cursor()
    prompt = "Develop a Pomodoro timer app using HTML, CSS, " \
             "and JavaScript. Allow users to set work and break" \
             " intervals and receive notifications when it's time to switch."

    # interactive terminal asking for prompt
    # receive_prompt()

    project_id = generate_code(prompt=prompt, cursor=cursor)

    execute_code(project_id=project_id)


if __name__ == '__main__':
    run()
