import os
import tempfile
import streamlit as st
from streamlit_chat import message
from langchain.chains import ConversationalRetrievalChain
from langchain.llms import HuggingFaceHub
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain.embeddings import HuggingFaceEmbeddings

# Function to initialize session state
def initialize_session_state():
    if 'history' not in st.session_state:
        st.session_state['history'] = []
    if 'generated' not in st.session_state:
        st.session_state['generated'] = ["Hello! Ask me anything about your documents."]
    if 'past' not in st.session_state:
        st.session_state['past'] = ["Hey! 👋"]
    if 'hf_api_key' not in st.session_state:
        st.session_state['hf_api_key'] = None

# Function to manage conversation flow
def conversation_chat(query, chain, history):
    result = chain({"question": query, "chat_history": history})
    history.append((query, result["answer"]))
    return result["answer"]

# Display chat history and handle user input
def display_chat_history(chain):
    reply_container = st.container()
    container = st.container()

    with container:
        with st.form(key='my_form', clear_on_submit=True):
            user_input = st.text_input("Question:", placeholder="Ask about your documents", key='input')
            submit_button = st.form_submit_button(label='Send')

        if submit_button and user_input:
            with st.spinner('Generating response...'):
                output = conversation_chat(user_input, chain, st.session_state['history'])
            st.session_state['past'].append(user_input)
            st.session_state['generated'].append(output)

    if st.session_state['generated']:
        with reply_container:
            for i in range(len(st.session_state['generated'])):
                message(st.session_state["past"][i], is_user=True, key=str(i) + '_user', avatar_style="thumbs")
                message(st.session_state['generated'][i], key=str(i), avatar_style="fun-emoji")

# Create conversational chain using two models (retriever + generator)
def create_conversational_chain(vector_store, hf_api_key):
    # Retrieve Model (Use text-generation task here for simplicity)
    retriever_llm = HuggingFaceHub(
        repo_id="google/flan-t5-small",  # A smaller text generation model for retrieval
        model_kwargs={"temperature": 0.01, "max_length": 500},
        huggingfacehub_api_token=hf_api_key
    )

    # Generator Model (Using a larger text generation model for answer generation)
    generator_llm = HuggingFaceHub(
        repo_id="google/flan-t5-large",  # A larger, more powerful model for generation
        model_kwargs={"temperature": 0.01, "max_length": 500},
        huggingfacehub_api_token=hf_api_key
    )

    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    # Create ConversationalRetrievalChain with two models: one for retrieval and one for generation
    chain = ConversationalRetrievalChain.from_llm(
        llm=generator_llm,  # Use generator for response generation
        chain_type="stuff",
        retriever=vector_store.as_retriever(search_kwargs={"k": 3}),  # Use retriever model to find relevant docs
        memory=memory
    )
    return chain

# Main function
def main():
    initialize_session_state()
    st.title("Multi-Docs ChatBot using Two Models (Retriever + Generator)")

    # User input for Hugging Face API token
    if not st.session_state['hf_api_key']:
        st.session_state['hf_api_key'] = st.text_input(
            "Enter your Hugging Face API token:", type="password"
        )
        if not st.session_state['hf_api_key']:
            st.warning("Please enter your Hugging Face API token to proceed.")
            return

    st.sidebar.title("Document Processing")
    uploaded_files = st.sidebar.file_uploader("Upload files", accept_multiple_files=True)

    if uploaded_files:
        text = []
        for file in uploaded_files:
            file_extension = os.path.splitext(file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file.read())
                temp_file_path = temp_file.name

            loader = None
            if file_extension == ".pdf":
                loader = PyPDFLoader(temp_file_path)
            elif file_extension == ".docx" or file_extension == ".doc":
                loader = Docx2txtLoader(temp_file_path)
            elif file_extension == ".txt":
                loader = TextLoader(temp_file_path)

            if loader:
                text.extend(loader.load())
                os.remove(temp_file_path)

        # Split the document into smaller chunks
        text_splitter = CharacterTextSplitter(separator="\n", chunk_size=1000, chunk_overlap=100, length_function=len)
        text_chunks = text_splitter.split_documents(text)

        # Create embeddings and vector store
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'device': 'cpu'})
        vector_store = FAISS.from_documents(text_chunks, embedding=embeddings)

        # Create the chain object
        chain = create_conversational_chain(vector_store, st.session_state['hf_api_key'])

        # Display the chat history and allow user interaction
        display_chat_history(chain)

if __name__ == "__main__":
    main()
