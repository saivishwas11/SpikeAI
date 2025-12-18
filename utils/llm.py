import time
from openai import OpenAI, APIError

# LiteLLM proxy details
BASE_URL = "http://3.110.18.218"
MODEL = "gemini-1.5-flash"

# ⚠️ Store key in environment variable in real setups
client = OpenAI(
    base_url=BASE_URL,
    api_key="YOUR_LITELLM_API_KEY"
)

MAX_RETRIES = 5
BASE_DELAY = 1  # seconds


def call_llm(messages):
    """
    Calls LiteLLM (Gemini) with exponential backoff for 429 errors.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.2
            )

            print(f"LLM call successful after {attempt + 1} attempt(s)")
            return response.choices[0].message.content

        except APIError as e:
            # Handle rate limiting
            if e.status_code == 429:
                wait_time = BASE_DELAY * (2 ** attempt)
                print(
                    f"Rate limited (429). "
                    f"Retrying in {wait_time}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(wait_time)
            else:
                print(f"LLM API error (status {e.status_code}): {e}")
                raise e

        except Exception as e:
            print(f"Unexpected LLM error: {e}")
            raise e

    # If all retries failed
    raise RuntimeError(
        "Failed to get LLM response after multiple retries due to rate limiting."
    )
