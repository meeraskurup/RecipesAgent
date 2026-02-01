import os
from dotenv import load_dotenv
from typing import Any
from pathlib import Path

# Add references
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FunctionTool, ToolSet, ListSortOrder, MessageRole
from user_functions import user_functions

def main(): 

    # Clear the console
    os.system('cls' if os.name=='nt' else 'clear')

    # Load environment variables from .env file
    load_dotenv()
    project_endpoint= os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")


    # Connect to the Agent client
    agent_client = AgentsClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential
            (exclude_environment_credential=True,
            exclude_managed_identity_credential=True)
    )
    
    # Define an agent that can use the custom functions
    with agent_client:

        functions = FunctionTool(user_functions)
        toolset = ToolSet()
        toolset.add(functions)
        agent_client.enable_auto_function_calls(toolset)
                
        agent = agent_client.create_agent(
            model=model_deployment,
            name="support-agent",
            instructions="""You are a recipe agent. 
                            The user will provide two images. One image is the grocery list for the week. 
                            Another image has the five main menu items or dishes to create. 
                            Using the provided grocery list and the five main menu items along with the descriptions, write out five recipes to follow. 
                            Ensure you provide recipes for the prepared ahead of time sauces if they are required. 
                            Ensure all items in the grocery list are used at least once among all five recipes. 
                            Assume pantry items like salt, pepper, sugar, flour, and others are needed for the recipes. 
                            Save the recipe in a text file and let the user know their recipes were created and saved.
                        """,
            toolset=toolset
        )
        thread = agent_client.threads.create()
        print(f"You're chatting with: {agent.name} ({agent.id})")

        # Loop until the user types 'quit'
        while True:
            # Get input image file paths
            img1_path = input("Enter path to grocery list image (or type 'quit' to exit): ")
            if img1_path.lower() == "quit":
                break
            img2_path = input("Enter path to menu items image (or type 'quit' to exit): ")
            if img2_path.lower() == "quit":
                break

            # Check if files exist
            if not (os.path.isfile(img1_path) and os.path.isfile(img2_path)):
                print("One or both image files do not exist. Please try again.")
                continue

            # Read images as binary
            with open(img1_path, "rb") as f1, open(img2_path, "rb") as f2:
                img1_data = f1.read()
                img2_data = f2.read()

            # Send images to the agent
            message = agent_client.messages.create(
                thread_id=thread.id,
                role="user",
                content="Please process these two images.",
                attachments=[
                    {"filename": os.path.basename(img1_path), "content": img1_data, "content_type": "image/jpeg"},
                    {"filename": os.path.basename(img2_path), "content": img2_data, "content_type": "image/jpeg"}
                ]
            )
            run = agent_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)

            # Check the run status for failures
            if run.status == "failed":
                print(f"Run failed: {run.last_error}")

            # Show the latest response from the agent
            last_msg = agent_client.messages.get_last_message_text_by_role(
                thread_id=thread.id,
                role=MessageRole.AGENT,
            )
            if last_msg:
                print(f"Last Message: {last_msg.text.value}")


        # Get the conversation history
        print("\nConversation Log:\n")
        messages = agent_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        for message in messages:
            if message.text_messages:
                last_msg = message.text_messages[-1]
                print(f"{message.role}: {last_msg.text.value}\n")


        # Clean up
        agent_client.delete_agent(agent.id)
        print("Deleted agent")

if __name__ == '__main__': 
    main()
