from openai import OpenAI
client=OpenAI(api_key = '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')

my_assistants = client.beta.assistants.list(
    order="desc",
    limit="20",
)
print(my_assistants.data)
