import os
import evadb
import subprocess
import pandas as pd


DEFAULT_PROMPT_PATH = "default_prompts/password_generator/prompt"
os.environ["OPENAI_API_KEY"] = \
    os.environ.get("OPENAI_API_KEY", "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")
os.environ["OPENAI_KEY"] = os.environ["OPENAI_API_KEY"]

SUMMARY_PATH = os.path.join("temp", "summary.csv")

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
        api_key = os.environ["OPENAI_API_KEY"]
    except KeyError:
        api_key = str(input("🔑 Enter your OpenAI key: "))
        os.environ["OPENAI_API_KEY"] = api_key

    return prompt


def read_coding_lib(code_dir, file_dict):
    for file_name in os.listdir(code_dir):
        file_path = f"{code_dir}/{file_name}"
        if os.path.isdir(file_path):
            read_coding_lib(code_dir=file_path, file_dict=file_dict)
        else:
            with open(file_path, "r") as f:
                file_dict[file_name] = f.read()


def generate_response(cursor: evadb.EvaDBCursor, question: str) -> str:
    """Generates question response with llm.

    Args:
        cursor (EVADBCursor): evadb api cursor.
        question (str): question to ask to llm.

    Returns
        str: response from llm.
    """

    if len(cursor.table("Transcript").select("text").df()["transcript.text"]) == 1:
        return (
            cursor.table("Transcript")
            .select(f"ChatGPT('{question}', text)")
            .df()["chatgpt.response"][0]
        )
    else:
        # generate summary of the video if its too long
        if not os.path.exists(SUMMARY_PATH):
            generate_summary(cursor)

        return (
            cursor.table("Summary")
            .select(f"ChatGPT('{question}', summary)")
            .df()["chatgpt.response"][0]
        )



if __name__ == '__main__':
    # prompt = receive_prompt()
    #
    # prompt_path = "temp/prompt"
    # if not os.path.exists("temp"):
    #     os.makedirs("temp")
    #
    # with open(prompt_path, "wb") as f:
    #     f.write(prompt)

    project_path = f"{os.getcwd()}/temp"
    # print(f"Creating the project inside {project_path}")
    # print("-*-*" * 30)
    # command = ["gpt-engineer", "temp/"]
    # proc = subprocess.run(command, text=True)

    code_contents = {}
    project_path = f"{project_path}/workspace"
    read_coding_lib(code_dir=project_path, file_dict=code_contents)

    # df = pd.DataFrame(code_contents, index=[0])

    cursor = evadb.connect().cursor()
    # a = cursor.query("SHOW FUNCTIONS;").df()
    # print(a)

    df = pd.DataFrame([{"summary": code_contents["all_output.txt"]}])

    df.to_csv(SUMMARY_PATH)

    cursor.drop_table("Summary", if_exists=True).execute()
    cursor.query(
        """CREATE TABLE IF NOT EXISTS Summary (summary TEXT(100));"""
    ).execute()
    cursor.load(SUMMARY_PATH, "Summary", "csv").execute()


    generate_summary_rel = cursor.table("Summary").select(
        "ChatGPT('summarize in detail', summary)"
    )
    responses = generate_summary_rel.df()["chatgpt.response"]
    summary = " ".join(responses)

    print()
