#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"

class INetworkingWebSocket;
class IWebSocketServer;

/** Hosts a localhost WebSocket server; runs MCP `run` requests on the game thread. */
class FMcpWebSocketServer : public TSharedFromThis<FMcpWebSocketServer>
{
public:
	// Defined in the .cpp where IWebSocketServer is complete, so the
	// TUniquePtr<IWebSocketServer> member can destroy through a full type.
	FMcpWebSocketServer();
	~FMcpWebSocketServer();

	/** Start listening on the configured port. Returns false on bind failure. */
	bool Start();
	/** Stop listening and drop connections. */
	void Stop();

	/** Pump the server. Called each tick. */
	void Tick();

private:
	void OnClientConnected(INetworkingWebSocket* ClientSocket);
	void HandleMessage(INetworkingWebSocket* ClientSocket, const FString& Message);
	void SendFrame(INetworkingWebSocket* ClientSocket, const FString& Json);

	// IWebSocketNetworkingModule::CreateServer() returns a TUniquePtr<IWebSocketServer>
	// in UE 5.7, so hold it as a TUniquePtr (move-assigned from CreateServer()).
	TUniquePtr<IWebSocketServer> Server;
	// Usage is one connection at a time (the Python MCP client). Track the single
	// active client so a deferred reply can be gated on it still being connected.
	INetworkingWebSocket* ActiveClient = nullptr;
	FTSTicker::FDelegateHandle TickHandle;
};
