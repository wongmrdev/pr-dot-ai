#!/usr/bin/env python3

import os
import sys
import subprocess
import openai
import tiktoken


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
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} branch1 ")
        sys.exit(1)

    branch1 = sys.argv[1]

    # Assuming that the openai API key is stored in the OPENAI_API_KEY environment variable
    # Split Length is set to 800, which is ~50% of the max token limit of the gpt-3.5-turbo model
    # This leaves enough tokens for the user and system prompts and the response from the API
    openai.api_key = os.environ["OPENAI_API_KEY"]

    # The gpt-3.5-turbo model is used by default
    # The user can pass in a different model as the second argument
    if len(sys.argv) == 3:
        gpt_model = sys.argv[2]
    else:
        gpt_model = "gpt-3.5-turbo-16k"
        # gpt_model = "gpt-4-0613"

    # Get the git diff for the branch
    diff_command = ["git", "diff", branch1]
    diff_output = subprocess.run(diff_command, capture_output=True, text=True)

    if diff_output.returncode != 0:
        print("Error in git diff command")
        sys.exit(1)

    diff_text = diff_output.stdout

    max_tokens_for_model = get_max_tokens(gpt_model)
    print(f"Max context length: {max_tokens_for_model}")
    # User and System prompts to fetch the summary of code changes for each split
    user_prompt_code_summary = (
        " Summarize the code changes from the git diff below. \n"
        " These summaries will later be used to generate a Pull Request Description.\n"
        " Keep the summaries very short and concise, focus only on high level functionality changes\n"
        " Ignore changes to pacakge versions changes \n"
        " For each major change, provide a short explanation of what was done and why. "
        " Highlight any parts of the code that may be controversial or need careful review. "
    )
    user_prompt_code_summary_tokens = num_tokens_from_message(user_prompt_code_summary)

    system_prompt_code_summary = (
        "You are a world class developer summarizing code changes.\n"
    )
    system_prompt_code_summary_tokens = num_tokens_from_message(
        system_prompt_code_summary
    )

    # User and System prompts to fetch the Pull Request Description
    user_prompt_pr_description = (
        "Create a concise, yet meaningful, Pull Request Description based on the following code changes. "
        "Your response should be formatted in Markdown and include the following headers, using ## Markdown styling: "
        " 1. Description,"
        " 2. Verification Steps,"
        " 3. Screenshots or Helpful Links,"
        " 4. Feedback.\n"
    )
    user_prompt_pr_description_tokens = num_tokens_from_message(
        user_prompt_pr_description
    )

    system_prompt_pr_description = (
        "You are a world class developer writing a Pull Request Description. \n"
    )
    system_prompt_pr_description_tokens = num_tokens_from_message(
        system_prompt_pr_description
    )

    final_response_context_tokens = 1500  # tokens
    desired_pr_length_in_tokens = (
        max_tokens_for_model
        - final_response_context_tokens
        - user_prompt_pr_description_tokens
        - system_prompt_pr_description_tokens
    )
    response_context_code_summary_ratio = 0.1
    response_context_code_summary_tokens = int(
        max_tokens_for_model * response_context_code_summary_ratio
    )
    print(f"Desired PR length in tokens: {desired_pr_length_in_tokens}")
    split_tokens = int(
        max_tokens_for_model
        - user_prompt_code_summary_tokens
        - system_prompt_code_summary_tokens
        - response_context_code_summary_tokens
    )
    print(f"Split message tokens: {split_tokens}")
    diff_splits = split_diff(diff_text, split_tokens)
    nbr_of_splits = len(diff_splits)
    print(f"Number of splits: {nbr_of_splits}")
    if (
        nbr_of_splits * response_context_code_summary_tokens
        > desired_pr_length_in_tokens
    ):
        print(
            f"Too many splits. Use a model with more max tokens or decrease split response context tokens"
        )
        sys.exit(1)

    # Call the ChatCompletion API for each split to get the summary of changes
    diff_summary = ""
    for i, diff_split in enumerate(diff_splits):
        print(f"Split length: {len(diff_split)}")
        print(f"Split tokens: {num_tokens_from_message(diff_split)}")
        print(f"Sending chunk {i+1} to OpenAI:")

        split_summary_response = openai.ChatCompletion.create(
            model=gpt_model,
            messages=[
                {"role": "user", "content": user_prompt_code_summary + diff_split},
                {"role": "system", "content": system_prompt_code_summary},
            ],
            max_tokens=response_context_code_summary_tokens,
        )

        split_summary = split_summary_response["choices"][0]["message"]["content"]
        diff_summary += split_summary
        print(f"Response from OpenAI API for chunk {i+1}:")
        print(split_summary)

    print(f"Sending OpenAI API a request to generate PR Summary:")
    pr_summary_response = openai.ChatCompletion.create(
        model=gpt_model,
        messages=[
            {"role": "user", "content": user_prompt_pr_description + diff_summary},
            {"role": "system", "content": system_prompt_pr_description},
        ],
    )

    pr_summary = pr_summary_response["choices"][0]["message"]["content"]
    print(f"Response from OpenAI API for PR Summary:")
    print(pr_summary)


# Split the diff into chunks of length split_token.
# Each split ends at the closest newline after the end of the split
# and starts at the 10th closest newline before the start of the split.
# This is done to ensure that the diff is split at a logical point and
# has an overlap of 10 lines with the previous split to provide context.
def split_diff(diff_text, split_token):
    print(f"diff_text length: {len(diff_text)}")
    if split_token <= 0 or len(diff_text) == 0:
        raise ValueError("Max length must be greater than 0.")
    diff_text_tokens = num_tokens_from_message(diff_text)
    print(f"diff_text_tokens: {diff_text_tokens}")
    diff_splits = []
    tracking_splits = []
    start = 0
    end = 0
    last_diff_text_index = len(diff_text) - 1
    starting_end_guess_distance = split_token
    while True:
        print(f"start: {start}")
        print(f"end: {end}")
        # We reached the last split
        if start >= last_diff_text_index:
            break
        if end >= last_diff_text_index:
            end = last_diff_text_index
            diff_splits.append(diff_text[start:end])
            tracking_splits.append((start, end))
            print(f"tracking_splits: {tracking_splits}")
            break
        else:
            while True:
                token_differance = split_token - num_tokens_from_message(
                    diff_text[start:end]
                )
                if token_differance <= 10:
                    break
                if end >= last_diff_text_index:
                    end = last_diff_text_index
                    break
                else:
                    end += min(1000, token_differance)
            diff_splits.append(diff_text[start:end])
            print(f"diff_split_tokens: {num_tokens_from_message(diff_text[start:end])}")
            tracking_splits.append((start, end))
            print(f"tracking_splits: {tracking_splits}")

            if end == last_diff_text_index:
                # We reached the last split
                break
            else:
                # Set the start of the next split
                start = end - 1000  # Give 1000 characters of overlap for context
    return diff_splits


# Find the nth closest newline before the given index
# Returns -1 if no nth newline is found before the given index
def find_nth_closest_newline_before(string, index, n):
    newline_count = 0
    for i in range(index, -1, -1):
        if string[i] == "\n":
            newline_count += 1
            if newline_count == n:
                return i
    return -1  # No nth newline found before the given index


# Find the nth closest newline after the given index
# Returns -1 if no nth newline is found after the given index
def find_nth_closest_newline_after(string, index, n):
    newline_count = 0
    for i in range(index, len(string)):
        if string[i] == "\n":
            newline_count += 1
            if newline_count == n:
                return i
    return -1  # No nth newline found after the given index


def get_max_tokens(model_name):
    model_data = {
        "gpt-4": 8192,
        "gpt-4-0613": 8192,
        "gpt-4-32k": 32768,
        "gpt-4-32k-0613": 32768,
        "gpt-3.5-turbo": 4096,
        "gpt-3.5-turbo-16k": 16384,
        "gpt-3.5-turbo-0613": 4096,
        "gpt-3.5-turbo-16k-0613": 16384,
        "text-davinci-003": 4097,
        "text-davinci-002": 4097,
        "code-davinci-002": 8001,
    }

    if model_name in model_data:
        return model_data[model_name]
    else:
        return None


def num_tokens_from_message(message, model="gpt-3.5-turbo-0613"):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        print(
            "Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613."
        )
        return num_tokens_from_message(message, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        print(
            "Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613."
        )
        return num_tokens_from_message(message, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_message() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    num_tokens += tokens_per_message
    num_tokens += len(encoding.encode(message))
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


if __name__ == "__main__":
    main()
