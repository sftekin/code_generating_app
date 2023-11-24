import os
import argparse
import subprocess
import glob
import time
import pickle as pkl

import evadb
from transformers import pipeline

from helper import read_all_prompts

DEFAULT_PROMPT_PATH = "default_prompts/password_generator/prompt"
os.environ["OPENAI_API_KEY"] = \
    os.environ.get("OPENAI_API_KEY", "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")
os.environ["OPENAI_KEY"] = os.environ["OPENAI_API_KEY"]


def receive_prompt():
    # we will return the prompt str
    print("Welcome to EvaDB, you can create any coding project on your local. "
          "\nYou only need to supply a prompt describing your coding project"
          " and an OpenAI API key.")
    prompt = str(
        input(
            "Enter the prompt describing your code. "
        )
    )

    # get OpenAI key if needed
    try:
        os.environ["OPENAI_API_KEY"]
    except KeyError:
        api_key = str(input("🔑 Enter your OpenAI key: "))
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_KEY"] = api_key

    return prompt


class CodeGenerator:
    def __init__(self, run_mode, reset=True):
        # we will store the codes inside a temp folder
        self.project_dir = f"{os.getcwd()}/temp"
        self.cursor = evadb.connect().cursor()
        self.run_mode = run_mode
        self.table_created = False
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
            self.table_created = True

    def check_prompt_sim(self, input_prompt):
        if not self.table_created:
            return False, None

        table = self.cursor.query("SELECT project_id, prompt FROM prompts;").execute().frames

        comp_prompts = []
        for i, row in table.iterrows():
            row_prompt = row["prompt"].replace("(", "").replace(")", "")
            compare_prompt = ". ".join([row_prompt.split(".")[0], input_prompt.split(".")[0]])
            comp_prompts.append(compare_prompt)
        response = self.pipe(comp_prompts)
        found_idx = [table.iloc[i]["project_id"] for i, r in enumerate(response) if r["label"] == "LABEL_1"]

        completed_idx = []
        for i in found_idx:
            all_output_path = f"{self.project_dir}/project-{i}/workspace/all_output.txt"
            if os.path.exists(all_output_path):
                completed_idx.append(i)

        if any(completed_idx):
            return True, completed_idx[0]
        else:
            return False, None

    def generate(self, prompt, ask_run=False):
        exists_flag, project_id = self.check_prompt_sim(input_prompt=prompt)
        if exists_flag:
            all_output_path = f"{self.project_dir}/project-{project_id}/workspace/all_output.txt"
            with open(all_output_path, "r") as f:
                all_output = f.read()

            if not ask_run:
                return

            print(all_output)
            answer = ""
            while answer not in ["y", "n"]:
                answer = input("Would you like to run the code y/n ?")

            if answer == "y":
                self.execute_code(project_id)
            else:
                return

        else:
            # no similar prompt has found
            project_path = self.get_project_path()
            prompt_path = f"{project_path}/prompt"
            with open(prompt_path, "w") as f:
                f.write(prompt)

            # generate the code by calling CodeGPT functionality
            run_mode = f"mode-{self.run_mode}"
            query = f"SELECT CodeGPT(\"{project_path}\", \"{run_mode}\");"
            self.cursor.query(query).df()

    def execute_code(self, project_id):
        project_path = f"{self.project_dir}/project-{project_id}"

        print(f"Executing the project-{project_id} inside {project_path}")
        print("-*-*" * 30)
        os.chdir(f"temp/project-{project_id}/workspace/")

        with open('run.sh', 'r+') as file:
            # Read the existing content
            content = file.read()

            # Move the cursor to the beginning of the file
            file.seek(0, 0)

            # Write new data at the beginning
            file.write('#!/bin/sh\n')

            # Write back the existing content
            file.write(content)

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


def run(default_prompt, run_mode, loop_test=False):
    if loop_test:
        assert run_mode == 3, "In loop test, the run mode must be 3"

    def_prompts = {}
    for prompt_dir in glob.glob("default_prompts/*"):
        prompt_name = os.path.basename(prompt_dir)
        with open(f"{prompt_dir}/prompt", "r") as f:
            def_prompts[prompt_name] = f.read()

    if loop_test:
        exec_time = []
        for i in range(5):
            print(f"****** ITERATION {i} ******")
            code_generator = CodeGenerator(run_mode=run_mode, reset=True)
            for prompt_name, prompt in def_prompts.items():
                start_time = time.time()
                code_generator.generate(prompt, ask_run=False)
                exec_time.append(time.time() - start_time)
        print(exec_time)
        with open("exec_time.pkl", "wb") as f:
            pkl.dump(exec_time, f)
    else:
        code_generator = CodeGenerator(run_mode=run_mode, reset=True)
        if default_prompt:
            prompt = def_prompts[default_prompt]
            code_generator.generate(prompt)
        else:
            # interactive terminal asking for prompt
            prompt = receive_prompt()
            code_generator.generate(prompt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Welcome to CodeGPT, a bot creates a '
                                                 'coding project for you')
    parser.add_argument('--default_prompt', type=str, default="pomodoro_timer",
                        choices=['file_explorer', 'markdown_editor', 'currency_converter',
                                 'image_resizer', 'timer_app', 'pomodoro_timer', 'todo_list',
                                 'url_shortener', 'file_organizer', 'password_generator'])
    parser.add_argument("--run_mode", type=int, default=3, choices=[1, 2, 3],
                        help="1: Standard mode bot ask for review and execution at the end\n"
                             "2: Bot asks for further clarifications if it is not certain\n"
                             "3: No execution just generation")
    parser.add_argument("--loop_test", action="store_true", help="iterates all the default prompts in a"
                                                                 " for loop to for 10 times")
    args = parser.parse_args()

    run(default_prompt=args.default_prompt,
        run_mode=args.run_mode,
        loop_test=args.loop_test)
