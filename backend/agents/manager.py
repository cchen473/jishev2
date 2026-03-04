from typing import List, Dict, Any, Sequence, Union
import asyncio
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.messages import TextMessage, BaseChatMessage
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import CancellationToken

# Import RAG engine
try:
    from backend.utils.rag_engine import retrieve_policy
except ImportError:
    from utils.rag_engine import retrieve_policy

class MissionManager:
    def __init__(self, callback=None):
        self.callback = callback

    async def run(self, mission_description: str):
        # Notify start
        if self.callback:
            await self.callback({
                "type": "status",
                "content": "Mission Started",
                "source": "SYSTEM"
            })

        # Define Agents with Mock Responses
        commander_initial = MockAgent(
            name="Commander_Agent",
            description="Commander of the mission",
            response_text=f"指挥官指令：收到警报 '{mission_description}'。启动紧急响应协议。CV_Analyst_Agent，请立即汇报现场视觉分析情况。"
        )

        cv_analyst = MockAgent(
            name="CV_Analyst_Agent",
            description="Computer Vision Expert",
            # Default response will be overridden by dynamic logic
            response_text=""
        )

        # Use the real RAG agent here
        policy_rag = PolicyRAGAgent(
            name="Policy_RAG_Agent",
            description="Policy Expert"
        )

        gis_routing = MockAgent(
            name="GIS_Routing_Agent",
            description="GIS Expert",
            response_text=""
        )

        commander_summary = MockAgent(
            name="Commander_Summary",
            description="Commander summary",
            response_text=""
        )
        
        agents = [commander_initial, cv_analyst, policy_rag, gis_routing, commander_summary]
        
        team = RoundRobinGroupChat(
            participants=agents,
            max_turns=5
        )

        # Run the team step-by-step to stream results
        # autogen-agentchat's run() method returns the final result, but we can stream messages?
        # RoundRobinGroupChat.run_stream() is available in newer versions or BaseGroupChat?
        # Let's check BaseChatAgent.run_stream.
        # But RoundRobinGroupChat inherits from BaseGroupChat.
        # If run_stream is available, we use it.
        
        # Manually iterate if stream is not easily available or just use run and capture events?
        # For now, let's use a simple approach: We can't easily hook into the *internal* message passing of RoundRobinGroupChat
        # without a custom runtime or using the stream method if it exists.
        # Let's try run_stream() if it exists on the team.
        
        # If run_stream is not available, we might need to implement a custom loop.
        # But autogen-agentchat 0.4+ usually supports streaming.
        
        stream = team.run_stream(task=f"System Alert: {mission_description}")
        
        async for message in stream:
            # message is a Stream item, which could be a TaskResult or a new message
            # Actually, run_stream yields messages as they are produced.
            
            if isinstance(message, TextMessage):
                if self.callback:
                    await self.callback({
                        "type": "TextMessage",
                        "content": message.content,
                        "source": message.source
                    })
            elif isinstance(message, TaskResult):
                # Final result
                pass
            else:
                 # Other events
                 pass

async def run_mission(mission_description: str) -> List[Dict[str, Any]]:
    # Legacy function for HTTP compatibility (optional)
    mgr = MissionManager()
    # We can't easily return history from run_stream unless we collect it.
    # For now, just return empty or adapt if needed.
    return []
