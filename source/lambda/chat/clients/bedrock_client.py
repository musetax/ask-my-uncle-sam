#!/usr/bin/env python
######################################################################################################################
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
######################################################################################################################

import os
from typing import Dict, Union
from uuid import UUID

from aws_lambda_powertools import Logger, Tracer
from clients.builders.bedrock_builder import BedrockBuilder
from clients.llm_chat_client import LLMChatClient
from llms.bedrock import BedrockLLM
from llms.rag.bedrock_retrieval import BedrockRetrievalLLM
from utils.constants import CONVERSATION_ID_EVENT_KEY, TRACE_ID_ENV_VAR, USER_ID_EVENT_KEY
from utils.enum_types import CloudWatchNamespaces, LLMProviderTypes
from utils.helpers import get_metrics_client

logger = Logger(utc=True)
tracer = Tracer()
metrics = get_metrics_client(CloudWatchNamespaces.COLD_STARTS)


class BedrockClient(LLMChatClient):
    def __init__(self, connection_id: str, rag_enabled: bool) -> None:
        super().__init__(connection_id=connection_id, rag_enabled=rag_enabled)

    def get_model(self, event_body: Dict, user_id: UUID) -> Union[BedrockLLM, BedrockRetrievalLLM]:
        super().get_model(event_body)

        self.builder = BedrockBuilder(
            self.llm_config,
            connection_id=self.connection_id,
            conversation_id=event_body[CONVERSATION_ID_EVENT_KEY],
            rag_enabled=self.rag_enabled,
        )
        model_name = self.llm_config.get("LlmParams", {}).get("ModelId", "anthropic.claude-3-5-sonnet-20240620-v1:0")
        self.construct_chat_model(user_id, event_body, LLMProviderTypes.BEDROCK.value, model_name)
        return self.builder.llm_model

    @tracer.capture_method
    def construct_chat_model(
        self, user_id: str, event_body: Dict, llm_provider: LLMProviderTypes, model_name: str
    ) -> None:
        conversation_id = event_body.get(CONVERSATION_ID_EVENT_KEY)
        if user_id and conversation_id:
            if not self.builder:
                logger.error(
                    f"Builder is not set for this LLMChatClient.",
                    xray_trace_id=os.environ[TRACE_ID_ENV_VAR],
                )
                raise ValueError(f"Builder is not set for this LLMChatClient.")

            self.builder.set_model_defaults(llm_provider, model_name)
            self.builder.validate_event_input_sizes(event_body)
            self.builder.set_knowledge_base()
            self.builder.set_conversation_memory(user_id, conversation_id)
            self.builder.set_llm_model()

        else:
            error_message = (
                f"Missing required parameters {USER_ID_EVENT_KEY}, {CONVERSATION_ID_EVENT_KEY} in the event."
            )
            logger.error(error_message, xray_trace_id=os.environ[TRACE_ID_ENV_VAR])
            raise ValueError(error_message)
