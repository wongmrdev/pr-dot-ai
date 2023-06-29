#!/usr/bin/env python3

import os
import sys
import subprocess
import openai

# This script takes in a branch name and generates a Pull Request Description
# based on the code changes in the branch. It uses the OpenAI ChatCompletion API
# to generate the Pull Request Description.

# The git diff is split into chunks and each chunk is sent to the OpenAI API
# to generate a summary of the code changes. The summaries of all the chunks
# are then sent to the OpenAI API to generate the Pull Request Description.

# We use this two step approach to get around the token limit of the models.
# Subsequent calls to the API are memoryless and require use to provide the
# user and assistant prompts again to get the desired output. Hence, we split
# the diff into chunks and generate summaries for each chunk. We then send
# all the summaries to the API to generate the Pull Request Description.
def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} branch1 ")
        sys.exit(1)

    branch1 = sys.argv[1]

    # Assuming that the openai API key is stored in the OPENAI_API_KEY environment variable
    # Split Length is set to 12000 which is ~75% of the max token limit of the gpt-3.5-turbo model
    # This leaves enough tokens for the user and system prompts and the response from the API
    openai.api_key = os.environ["OPENAI_API_KEY"]
    gpt_model = "gpt-3.5-turbo"
    split_length = 12000

    diff_command = ["git", "diff", branch1]
    diff_output = subprocess.run(diff_command, capture_output=True, text=True)

    if diff_output.returncode != 0:
        print("Error in git diff command")
        sys.exit(1)
    
    diff_text = diff_output.stdout
    diff_splits = split_diff(diff_text, split_length)

    # User and System prompts to fetch the summary of code changes for each split
    user_prompt_code_summary = (
        " Summarize the code changes from the git diff below. \n"
        " Make sure to include file and function names and focuse on the change in functionality \n"
        " These summaries will later be used to generate a Pull Request Description.\n"
    )

    system_prompt_code_summary = (
        "You are a world class developer summarizing code changes.\n"
    )

    # Call the ChatCompletion API for each split to get the summary of changes
    diff_summary = ""
    for i, diff_split in enumerate(diff_splits):
        print(f"Sending chunk {i+1} to OpenAI:")

        split_summary_response = openai.ChatCompletion.create(
            model=gpt_model,
            messages=[{"role": "user", "content": user_prompt_code_summary+diff_split},
                      {"role": "system", "content": system_prompt_code_summary}],
        )
        
        split_summary = split_summary_response["choices"][0]["message"]["content"]
        diff_summary += split_summary
        print(f"Response from OpenAI API for chunk {i+1}:")
        print(split_summary)

    # User and System prompts to fetch the Pull Request Description
    user_prompt_pr_description = (
        "We would like to create a Pull Request Description based on the summary of code changes below. \n"
        " Reply with Markdown format.\n"
        " Include these 4 headers in the PR output using ## Markdown styling: "
        " 1. Description,"
        " 2. How can reviewers verify the behavior?,"
        " 3. Screenshots or links that might help speedup the review,"
        " 4. Are you looking for feedback in a specific area?\n\n"
        " Highlight, in the description, the major functionality added or removed.\n"
        " If there are any changes to package.json file, please"
        " remind the reviewer to run yarn install after pulling changes."
    )

    system_prompt_pr_description = (
        "You are a world class developer writing a Pull Request Description. \n"
    )

    print(f"Sending OpenAI API a request to generate PR Summary:")

    pr_summary_response = openai.ChatCompletion.create(
        model=gpt_model,
        messages=[{"role": "user", "content": user_prompt_pr_description+diff_summary},
                    {"role": "system", "content": system_prompt_pr_description}],          
    )
    
    pr_summary = pr_summary_response["choices"][0]["message"]["content"]
    print(f"Response from OpenAI API for PR Summary:")
    print(pr_summary)

# Split the diff into chunks of length split_length.
# Each split ends at the closest newline after the end of the split
# and starts at the 10th closest newline before the start of the split.
# This is done to ensure that the diff is split at a logical point and
# has an overlap of 10 lines with the previous split to provide context.
def split_diff(diff_text, split_length):
    if split_length <= 0:
        raise ValueError("Max length must be greater than 0.")

    num_parts = -(-len(diff_text) // split_length)
    diff_splits = []

    for i in range(num_parts):
        # If this is not the first split, find the 10th closest newline before the start of the split
        if i != 0:
            start = find_nth_closest_newline_before(diff_text, end, 10) + 1
            assert start != -1
        else:
            start = 0
        
        # If this is not the last split, find the closest newline after the end of the split
        if i != num_parts - 1:
            end = find_nth_closest_newline_after(diff_text, start + split_length, 1)
            assert end != -1
        else:
            end = len(diff_text)

        diff_splits.append(diff_text[start:end])
        return diff_splits

# Find the nth closest newline before the given index
# Returns -1 if no nth newline is found before the given index
def find_nth_closest_newline_before(string, index, n):
    newline_count = 0
    for i in range(index, -1, -1):
        if string[i] == '\n':
            newline_count += 1
            if newline_count == n:
                return i
    return -1  # No nth newline found before the given index

# Find the nth closest newline after the given index
# Returns -1 if no nth newline is found after the given index
def find_nth_closest_newline_after(string, index, n):
    newline_count = 0
    for i in range(index, len(string)):
        if string[i] == '\n':
            newline_count += 1
            if newline_count == n:
                return i
    return -1  # No nth newline found after the given index

if __name__ == "__main__":
    main()
