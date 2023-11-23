import os
import evadb
import subprocess
import pandas as pd
from helper import read_coding_lib, read_all_prompts
from transformers import pipeline

# from dotenv import load_dotenv


DEFAULT_PROMPT_PATH = "default_prompts/password_generator/prompt"
os.environ["OPENAI_API_KEY"] = \
    os.environ.get("OPENAI_API_KEY", "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")
os.environ["OPENAI_KEY"] = os.environ["OPENAI_API_KEY"]


def receive_prompt():
    # we will return the prompt str
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


class CodeGenerator:
    def __init__(self, reset=True):
        # we will store the codes inside a temp folder
        self.project_dir = f"{os.getcwd()}/temp"
        self.cursor = evadb.connect().cursor()
        if reset:
            self.cursor.query("DROP TABLE IF EXISTS prompts;").execute()

        self.db_connected = False

        # load prompt similarity checker
        self.create_prompts_table()

        self.cursor.query(
            "CREATE FUNCTION IF NOT EXISTS CodeGPT IMPL 'code_gpt.py';"
        ).execute()

        self.pipe = pipeline("text-classification", model="AMHR/adversarial-paraphrasing-detector")

    def create_prompts_table(self):
        # self.cursor.query("DROP TABLE IF EXISTS prompts;").execute()
        self.cursor.query(
            """CREATE TABLE  IF NOT EXISTS prompts (project_id INTEGER, prompt TEXT(200));"""
        ).execute()
        prompts = {}
        read_all_prompts(code_dir=self.project_dir, file_dict=prompts)
        if prompts:
            for project, prompt in prompts.items():
                project_id = int(project.split("-")[1])
                query = f"INSERT INTO prompts (project_id, prompt) VALUES ({project_id}, \"({prompt})\");"
                self.cursor.query(query).execute()

    def check_prompt_sim(self, input_prompt):
        table = self.cursor.query("SELECT project_id, prompt FROM prompts;").execute().frames

        comp_prompts = []
        for i, row in table.iterrows():
            row_prompt = row["prompt"].replace("(", "").replace(")", "")
            compare_prompt = ". ".join([row_prompt.split(".")[0], input_prompt.split(".")[0]])
            comp_prompts.append(compare_prompt)
        response = self.pipe(comp_prompts)
        found_idx = [i + 1 for i, r in enumerate(response) if r["label"] == "LABEL_1"]

        completed_idx = []
        for i in found_idx:
            all_output_path = f"{self.project_dir}/project-{i}/workspace/all_output.txt"
            if os.path.exists(all_output_path):
                completed_idx.append(i)

        if any(completed_idx):
            return True, table.iloc[completed_idx[0]]["project_id"]
        else:
            return False, None

    def generate(self, prompt):
        exists_flag, project_id = self.check_prompt_sim(input_prompt=prompt)
        if exists_flag:
            all_output_path = f"{self.project_dir}/project-{project_id}/workspace/all_output.txt"
            with open(all_output_path, "r") as f:
                all_output = f.read()
            print(all_output)

            answer = ""
            while answer not in ["y", "n"]:
                answer = input("Would you like to run the code y/n ?")

            if answer == "y":
                self.execute_code(project_id)
            else:
                return

        project_path = self.get_project_path()
        prompt_path = f"{project_path}/prompt"
        with open(prompt_path, "w") as f:
            f.write(prompt)

        # generate the code by calling CodeGPT functionality
        query = f"SELECT CodeGPT(\"{project_path}\", \"\");"
        self.cursor.query(query).df()

    def execute_code(self, project_id):
        project_path = f"{self.project_dir}/project-{project_id}"

        print(f"Executing the project-{project_id} inside {project_path}")
        print("-*-*" * 30)
        os.chdir(f"temp/project-{project_id}/workspace/")
        command = ["chmod", "+x", "run.sh"]
        proc = subprocess.run(command, text=True)

        command = [f"./run.sh"]
        proc = subprocess.run(command, text=True)

    def get_project_path(self):
        if not os.path.exists(self.project_dir):
            os.makedirs(self.project_dir)
            file_index = 1
        elif len(os.listdir(self.project_dir)) == 0:
            file_index = 1
        else:
            # temp exits get the file_index
            file_indices = [int(file_name.split("-")[1])
                            for file_name in os.listdir(self.project_dir)]
            file_index = sorted(file_indices)[-1] + 1

        # write the prompt to a file in the temp directory
        project_path = f"{self.project_dir}/project-{file_index}"
        os.makedirs(project_path)

        return project_path


def run():
    code_generator = CodeGenerator()

    # prompt = "Develop a Pomodoro timer app using HTML, CSS, " \
    #          "and JavaScript. Allow users to set work and break" \
    #          " intervals and receive notifications when it's time to switch."

    prompt = "Create a simple to-do list app using HTML, CSS, and JavaScript." \
             " Store tasks in local storage and allow users to add, edit, and delete tasks."

    code_generator.generate(prompt)

    # interactive terminal asking for prompt
    # receive_prompt()

    # project_id = generate_code(prompt=prompt, cursor=cursor)
    #
    # execute_code(project_id=project_id)


if __name__ == '__main__':
    run()
