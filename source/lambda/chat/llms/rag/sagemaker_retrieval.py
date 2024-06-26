#!/usr/bin/env python
# *********************************************************************************************************************
#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.                                                #
#                                                                                                                    #
#  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance    #
#  with the License. A copy of the License is located at                                                             #
#                                                                                                                    #
#      http://www.apache.org/licenses/LICENSE-2.0                                                                    #
#                                                                                                                    #
#  or in the 'license' file accompanying this file. This file is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    #
#  and limitations under the License.                                                                                #
# ********************************************************************************************************************#

import os
import time
from typing import Any, Dict, Optional

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from langchain.chains import ConversationalRetrievalChain
from langchain_core.prompts import PromptTemplate
from llms.models.llm import LLM
from llms.sagemaker import SageMakerLLM
from shared.defaults.model_defaults import ModelDefaults
from utils.constants import DEFAULT_RAG_CHAIN_TYPE, DEFAULT_RETURN_SOURCE_DOCS, TRACE_ID_ENV_VAR
from utils.custom_exceptions import LLMInvocationError
from utils.enum_types import CloudWatchMetrics, CloudWatchNamespaces
from utils.helpers import get_metrics_client

tracer = Tracer()
logger = Logger(utc=True)
metrics = get_metrics_client(CloudWatchNamespaces.LANGCHAIN_LLM)


class SageMakerRetrievalLLM(SageMakerLLM):
    """
    SageMakerRetrievalLLM is a wrapper around the SageMaker LLM invocation. This class can generate chat responses, provided a conversation memory
    and knowledge base. Specifically, this enables the usage of RAG with SageMaker.

    Attributes:
    - llm_params: LLM dataclass object which has the following:
        api_token (str): Set to None for SageMaker models. Not required for SageMaker as a SageMaker client is used to invoke the SageMaker models.
        api_token (str): HuggingFace API token, which can be obtained from HuggingFace
        conversation_memory (BaseMemory): A BaseMemory object which helps store and access user chat history
        knowledge_base (KnowledgeBase): A KnowledgeBase object which retrieves information from the user's knowledge base for LLM context
        return_source_docs (bool): A boolean which represents whether the source documents are returned or not [optional, defaults to DEFAULT_RETURN_SOURCE_DOCS]
        model (str): HuggingFace model name that represents the underlying LLM model [optional, defaults to DEFAULT_MODELS_MAP[LLMProviderTypes.HUGGINGFACE.value]]
        model_params (dict): A dictionary of model parameters, which can be obtained from the HuggingFace [optional]
        prompt_template (str): A string which represents the prompt template [optional, defaults to prompt provided in ModelInfoStorage DynamoDB table]
        streaming (bool): A boolean which represents whether the chat is streaming or not [optional, defaults to streaming value in provided in ModelInfoStorage
            DynamoDB table]
        verbose (bool): A boolean which represents whether the chat is verbose or not [optional, defaults to DEFAULT_VERBOSE_MODE]
        temperature (float): A non-negative float that tunes the degree of randomness in model response generation [optional, defaults to temperature
            provided in ModelInfoStorage DynamoDB table]
        callbacks (list): A list of BaseCallbackHandler objects which are used for the LLM model callbacks [optional, defaults to None]

    - model_defaults (ModelDefaults): A ModelDefaults object which contains default values for the model retrieved from ModelInfoStorage DynamoDB table
    - sagemaker_endpoint_name (str): A string which represents the SageMaker endpoint name. The SageMaker endpoint is invoked with the user inputs to get
        chat responses
    - input_schema (dict): A dictionary of input schema for the SageMaker endpoint. This is passed to SageMaker Content Handler.
        The content handler is used to transform the input to the SageMaker endpoint as it expects, and then retrieve the response from the JSON response received.
        The input_schema represents the schema of the input to the SageMaker endpoint. The response_jsonpath below represents the path for the text output from the
        SageMaker endpoint. See SageMakerContentHandler for more information and examples available at llms/models/sagemaker/content_handler.py
    - response_jsonpath (str): A string which represents the jsonpath for the chat text output from the SageMaker endpoint
    - return_source_docs (bool): A boolean which represents whether the source documents are returned or not [optional, defaults to DEFAULT_RETURN_SOURCE_DOCS]

    Methods:
        generate(question): Generates a chat response
        get_conversation_chain(): Creates a `ConversationalRetrievalChain` chain that is connected to a conversation memory and the specified prompt
        get_validated_prompt(prompt_template, prompt_template_placeholders, default_prompt_template, default_prompt_template_placeholders): Generates the PromptTemplate using
            the provided prompt template and placeholders. In case of errors, falls back on default values.
    """

    def __init__(
        self,
        llm_params: LLM,
        model_defaults: ModelDefaults,
        sagemaker_endpoint_name: Optional[str],
        input_schema=Dict[str, Any],
        response_jsonpath=Dict[str, Any],
        return_source_docs=DEFAULT_RETURN_SOURCE_DOCS,
    ):
        self._condensing_prompt_template = PromptTemplate.from_template(model_defaults.disambiguation_prompt)
        self._return_source_docs = return_source_docs
        super().__init__(
            llm_params=llm_params,
            model_defaults=model_defaults,
            sagemaker_endpoint_name=sagemaker_endpoint_name,
            input_schema=input_schema,
            response_jsonpath=response_jsonpath,
            rag_enabled=True,
        )

    @property
    def condensing_prompt_template(self) -> bool:
        return self._condensing_prompt_template

    @property
    def return_source_docs(self) -> bool:
        return self._return_source_docs

    def get_conversation_chain(self) -> ConversationalRetrievalChain:
        """
        Creates a `ConversationalRetrievalChain` chain that uses a `retriever` connected to a knowledge base.
        Args: None

        Returns:
            ConversationalRetrievalChain: An LLM chain uses a `retriever` connected to a knowledge base.
        """
        return ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.knowledge_base.retriever,
            chain_type=DEFAULT_RAG_CHAIN_TYPE,
            verbose=self.verbose,
            memory=self.conversation_memory,
            return_source_documents=self.return_source_docs,
            combine_docs_chain_kwargs={"prompt": self.prompt_template},
            get_chat_history=lambda chat_history: chat_history,
            condense_question_llm=self.get_llm(condense_prompt_model=True),
            condense_question_prompt=self.condensing_prompt_template,
            callbacks=self.callbacks,
        )

    @tracer.capture_method(capture_response=True)
    def generate(self, question: str) -> Dict[str, Any]:
        """@overrides SageMakerLLM.generate

        Args:
            question (str): the question that should be sent to the LLM model

        Returns:
            (Dict): The LLM response message as a dictionary with the relevant source documents
            Response dict form:
            {
             "answer": str,
             "source_documents": List[Dict]
            }
        """
        error_message = f"Error occurred while invoking SageMaker endpoint: '{self.sagemaker_endpoint_name}'. "
        logger.info(
            f"Prompt for LLM: {self.prompt_template.template.replace('{input}', '{question}').replace('{history}', '{chat_history}')}"
        )
        logger.debug(f"Condensing prompt for LLM: {self.condensing_prompt_template.template}")

        with tracer.provider.in_subsegment("## llm_chain") as subsegment:
            subsegment.put_annotation("library", "langchain")
            subsegment.put_annotation("operation", "ConversationalRetrievalChain")
            metrics.add_metric(
                name=CloudWatchMetrics.LANGCHAIN_QUERY.value,
                unit=MetricUnit.Count,
                value=1,
            )
            metrics.flush_metrics()

            try:
                start_time = time.time()
                chain_result = self.conversation_chain.invoke(
                    {
                        "question": question,
                        "chat_history": self.conversation_memory.chat_memory.messages,
                    },
                )
                end_time = time.time()
                metrics.flush_metrics()

                metrics.add_metric(
                    name=CloudWatchMetrics.LANGCHAIN_QUERY_PROCESSING_TIME.value,
                    unit=MetricUnit.Seconds,
                    value=(end_time - start_time),
                )
                metrics.flush_metrics()

                logger.debug(f"LLM response: {chain_result}")
                llm_response = {"answer": chain_result["answer"].strip()}
                if "source_documents" in chain_result:
                    llm_response["source_documents"] = chain_result["source_documents"]

                return llm_response
            except ValueError as ve:
                error_message = error_message + str(ve)
                logger.error(error_message, xray_trace_id=os.environ[TRACE_ID_ENV_VAR])
                metrics.add_metric(name=CloudWatchMetrics.LANGCHAIN_FAILURES.value, unit=MetricUnit.Count, value=1)
                raise LLMInvocationError(error_message)
            except Exception as ex:
                error_message = error_message + str(ex)
                logger.error(error_message, xray_trace_id=os.environ[TRACE_ID_ENV_VAR])
                metrics.add_metric(name=CloudWatchMetrics.LANGCHAIN_FAILURES.value, unit=MetricUnit.Count, value=1)
                raise LLMInvocationError(str(ex))
            finally:
                metrics.flush_metrics()
