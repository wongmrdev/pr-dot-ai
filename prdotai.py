#!/usr/bin/env python3

import os
import sys
import subprocess
import openai


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

    # Initial prompt with the headers for the PR
    initial_prompt = (
        "We would like to create a Pull Request Description based on the git diff."
        " We prefer concise descriptions, so please try to keep it short."
        " Highlight the major changes and the improvements made."
        " If there are any changes to package.json dependencies, please mention them "
        " only if there are new dependencies or if any dependency version was updated"
        " and remind the reader to run yarn install after pulling changes."
        " Reply with Markdown format."
        " Include these 4 headers in the PR output using ## Markdown styling: "
        " Description,"
        " How can reviewers verify the behavior?,"
        " Screenshots or links that might help speedup the review,"
        " Are you looking for feedback in a specific area?\n\n"
    )

    diff_text = initial_prompt + diff_output.stdout
    chunks = split_prompt(diff_text, 24000)

    pr_description = ""

    for i, chunk in enumerate(chunks):
        print(f"Sending chunk {i+1} to OpenAI API...")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": chunk["content"]}],
        )

        response_text = response["choices"][0]["message"]["content"]
        print(f"Response from OpenAI API for chunk {i+1}:\n\n")
        print(response_text)
        pr_description += response_text

    print("\n\nFull PR description:\n\n")
    print(pr_description)


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
            part_msg += "\nALL PARTS SENT. Now you can continue processing the request."
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


if __name__ == "__main__":
    main()
