# Pull Request Description Generator

This is a command-line tool that uses OpenAI's GPT-3 model to generate pull request descriptions based on the `git diff` of a specified branch.

## Prerequisites
- Python 3.7 or above
- Git
- An OpenAI API key

## Setup
1. Clone this repository.
```bash
git clone https://github.com/wongmrdev/prdotai.git
cd prdotai
```
2. Install dependencies
```bash
   pip install openai python-dotenv
```

3. Set openai API key

```bash
export OPENAI_API_KEY=your_openai_key
```

4. Make file executable and set global symbolic link

```bash
chmod +x prdotai.py
ln -s /path/to/your/prdotai.py /usr/local/bin/prdotai
```

## Usage

From any git tracked directory, from any branch, generate PR comparing current branch to specified branch
```bash
prdotai <branch1>
```

## Example usage (on feature branch)
```bash
prdotai main
```

## Example output

```markdown
## Description
We have made changes to the LICENSE file, updating the copyright holder's name from "M Wong" to "Matt Wong." We have also added a new README.md file that provides information about the project, its prerequisites, setup instructions, and usage examples. Additionally, we have added a new Python script called "prdotai.py" that generates pull request descriptions based on the git diff of a specified branch.

## How can reviewers verify the behavior?
Reviewers can verify the behavior by comparing the changes made in the LICENSE file and the addition of the README.md and prdotai.py files.

## Screenshots or links that might help speed up the review
N/A

## Are you looking for feedback in a specific area?
We are looking for feedback on the accuracy and clarity of the generated pull request descriptions.
```
