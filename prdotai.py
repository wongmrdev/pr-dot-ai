#!/usr/bin/env python3

import os
import sys
import subprocess
import openai
import tiktoken
from pick import pick


# Add a system prompt to get more context
# Chunk based on Tokens not Characters
# Send the "prompt" as the last message
# Increase the output Tokens
# Choose the max_tokens based on the model
# Use the temperature parameter to control the randomness of the output


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} branch1 ")
        sys.exit(1)

    branch1 = sys.argv[1]

    # Assuming that the openai API key is stored in the OPENAI_API_KEY environment variable
    openai.api_key = os.getenv("OPENAI_API_KEY")

    diff_command = ["git", "diff", branch1]
    diff_output = subprocess.run(diff_command, capture_output=True, text=True)

    if diff_output.returncode != 0:
        print("Error in git diff command")
        sys.exit(1)

    # Get the list of available models
    model_list = openai.Model.list()["data"]
    model_names = [model["id"] for model in model_list]
    model_name, index = pick(model_names, "Choose a model:")

    # Initial prompt with the headers for the PR
    initial_prompt = (
        "We would like to create a Pull Request Description based on the git diff I just sent you.\n"
        " Please reply with Markdown format.\n"
        " Include these 4 headers in the PR output using ## Markdown styling: "
        " Description,"
        " How can reviewers verify the behavior?,"
        " Screenshots or links that might help speedup the review,"
        " Are you looking for feedback in a specific area?\n\n"
        " Highlight, in the description, the major functionality added or removed.\n"
        " Only remind the reviewer to run yarn install if there are any changes to the file package.json"
        " Don't send a response now because I'm going to send you the diff in chunks."
    )

    diff_chunks = split_prompt(diff_output.stdout, split_length=24000)

    pr_description = ""
    system_prompt = "You are helpful assistant. You are helping me write a Pull Request Description."
    response = openai.ChatCompletion.create(
        model=model_name,
        messages=[
            {"role": "user", "content": initial_prompt},
            {"role": "system", "content": system_prompt},
        ],
        # temperature=0.5,
        # max_tokens=4000,
    )
    print(response["choices"][0]["message"]["content"])

    for i, chunk in enumerate(diff_chunks):
        print(f"Sending chunk {i+1} to OpenAI API...")
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[{"role": "user", "content": chunk["content"]}],
            # temperature=0.5,
            # max_tokens=20,
        )

        response_text = response["choices"][0]["message"]["content"]
        print(f"Response from OpenAI API for chunk {i+1}:")
        print(response_text)
        pr_description += response_text

    # print("\n\nFull PR description:\n\n")
    # print(pr_description)


def split_prompt(text, split_length):
    if split_length <= 0:
        raise ValueError("Max length must be greater than 0.")

    num_parts = -(-len(text) // split_length)
    file_data = []

    for i in range(num_parts):
        start = i * split_length
        end = min((i + 1) * split_length, len(text))

        if i == num_parts - 1:
            part_msg = f"[START PART {i + 1}/{num_parts}]\n"
            part_msg += text[start:end] + f"\n[END PART {i + 1}/{num_parts}]"
            part_msg += "\nALL PARTS SENT. Now you can give the Pull Request in the format requested"
        else:
            part_msg = (
                f"Do not answer yet. This is just another part of the text I want to send you."
                ' Just receive and acknowledge as "Part {i + 1}/{num_parts} received"'
                " and wait for the next part.\n[START PART {i + 1}/{num_parts}]\n"
                + text[start:end]
                + f"\n[END PART {i + 1}/{num_parts}]"
                "\nRemember not answering yet. Just acknowledge you received this part"
                ' with the message "Part {i + 1}/{num_parts} received" and wait for the next part.'
            )

        file_data.append(
            {
                "name": f"split_{str(i + 1).zfill(3)}_of_{str(num_parts).zfill(3)}.txt",
                "content": part_msg,
            }
        )

    return file_data


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


if __name__ == "__main__":
    main()
