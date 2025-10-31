#! /usr/bin/env python
"""Generate changelog using OpenAI's API based on commit messages."""
import os
import sys
import openai

def main():
    """
    Generates a changelog using OpenAI's API based on commit messages.

    This script reads commit messages from stdin, combines them with a prompt template,
    and sends the request to OpenAI to generate a structured changelog.

    The following environment variables are required:
    - ARK_API_KEY: Your OpenAI API key.
    - ARK_MODEL_ENDPOINT: The endpoint for the OpenAI model.

    The script also accepts two command-line arguments:
    - new_tag: The new version tag.
    - previous_tag: The previous version tag.
    """
    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        print("Error: ARK_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    api_url = os.getenv("ARK_MODEL_ENDPOINT")
    if not api_url:
        print("Error: ARK_MODEL_ENDPOINT environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = openai.OpenAI(api_key=api_key,base_url=api_url)
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <new_tag> <previous_tag>", file=sys.stderr)
        sys.exit(1)

    new_tag = sys.argv[1]
    previous_tag = sys.argv[2]

    try:
        with open(".github/prompts/changelog_prompt.md", "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        print("Error: Prompt template file not found at .github/prompts/changelog_prompt.md", file=sys.stderr)
        sys.exit(1)

    commit_logs = sys.stdin.read()

    prompt = prompt_template.replace("<now_tag>", new_tag).replace("<pre_tag>", previous_tag)

    final_prompt = f"{prompt}\n\n**Raw Release Notes Data:**\n\n{commit_logs}"

    try:
        model = os.getenv("ARK_MODEL_NAME", "doubao-seed-1-6-251015")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates changelogs."},
                {"role": "user", "content": final_prompt},
            ],
            temperature=0.7,
            top_p=1,
        )
        changelog = response.choices[0].message.content
        print(changelog)
    except openai.APIError as e:
        print(f"Error calling OpenAI API with prompt: {final_prompt}: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
