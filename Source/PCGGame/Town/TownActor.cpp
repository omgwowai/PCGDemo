// Copyright Epic Games, Inc. All Rights Reserved.

#include "TownActor.h"

#include "TownStyleData.h"
#include "PCGGame.h"

#include "PCGComponent.h"
#include "PCGGraph.h"
#include "PCGNode.h"
#include "Elements/PCGCreateAttribute.h"
#include "Elements/PCGStaticMeshSpawner.h"
#include "MeshSelectors/PCGMeshSelectorWeighted.h"
#include "Engine/StaticMesh.h"

namespace
{
	// Parameter-node titles in the town graph (see create_town_pcg_graph_v5.py).
	const FString ModeSwitchTitle = TEXT("MODE SWITCH");
	const FString RoadSourceTitle = TEXT("ROAD SOURCE SWITCH");
	const FString SizeFullTitle = TEXT("SIZE GridExtents Full");
	const FString SizeCandTitle = TEXT("SIZE GridExtents Cand");
	const FString SizeBlockTitle = TEXT("SIZE GridExtents Block");
	const FString SizeMaxDistTitle = TEXT("SIZE MaxDistance");

	UPCGCreateAttributeSetSettings* FindParamNode(UPCGGraph* Graph, const FString& TitleContains)
	{
		for (UPCGNode* Node : Graph->GetNodes())
		{
			if (!Node || !Node->GetAuthoredTitleName().ToString().Contains(TitleContains))
			{
				continue;
			}
			if (UPCGCreateAttributeSetSettings* Settings = Cast<UPCGCreateAttributeSetSettings>(Node->GetSettings()))
			{
				return Settings;
			}
		}
		return nullptr;
	}
}

ATownActor::ATownActor(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
}

void ATownActor::RegenerateTown()
{
	const bool bParamsOk = ApplyParametersToGraph();
	const bool bStyleOk = ApplyStyleToGraph();
	ScaleVolumeToTown();

	if (PCGComponent)
	{
		PCGComponent->Cleanup(/*bRemoveComponents=*/true);
		PCGComponent->Generate(/*bForce=*/true);
	}

	UE_LOG(LogPCGGame, Log, TEXT("TownActor '%s': regenerate (params %s, style %s)"),
		*GetName(), bParamsOk ? TEXT("ok") : TEXT("SKIPPED"), bStyleOk ? TEXT("ok") : TEXT("SKIPPED"));
}

bool ATownActor::ApplyParametersToGraph()
{
	UPCGGraph* Graph = PCGComponent ? PCGComponent->GetGraph() : nullptr;
	if (!Graph)
	{
		return false;
	}

	bool bAllFound = true;
	// Changing settings values in place bypasses the graph-executor cache; a
	// generate would silently reuse results computed for the old values.
	// Routing through PostEditChangeProperty runs the same notification chain
	// as a Details-panel edit (settings-changed broadcast + CacheCrc).
	// UPCGSettings redeclares it protected, but UObject's declaration is
	// public — calling through UObject* still virtual-dispatches correctly.
	auto Commit = [](UPCGSettings* S)
	{
		S->Modify();
#if WITH_EDITOR
		FPropertyChangedEvent Event(nullptr);
		static_cast<UObject*>(S)->PostEditChangeProperty(Event);
#endif
	};
	auto SetBool = [&](const FString& Title, bool bValue)
	{
		if (UPCGCreateAttributeSetSettings* S = FindParamNode(Graph, Title))
		{
			S->AttributeTypes.Type = EPCGMetadataTypes::Boolean;
			S->AttributeTypes.BoolValue = bValue;
			Commit(S);
		}
		else
		{
			bAllFound = false;
		}
	};
	auto SetVector = [&](const FString& Title, const FVector& Value)
	{
		if (UPCGCreateAttributeSetSettings* S = FindParamNode(Graph, Title))
		{
			S->AttributeTypes.Type = EPCGMetadataTypes::Vector;
			S->AttributeTypes.VectorValue = Value;
			Commit(S);
		}
		else
		{
			bAllFound = false;
		}
	};
	auto SetDouble = [&](const FString& Title, double Value)
	{
		if (UPCGCreateAttributeSetSettings* S = FindParamNode(Graph, Title))
		{
			S->AttributeTypes.Type = EPCGMetadataTypes::Double;
			S->AttributeTypes.DoubleValue = Value;
			Commit(S);
		}
		else
		{
			bAllFound = false;
		}
	};

	const double Half = TownHalfSize;
	SetBool(ModeSwitchTitle, bRenderMeshes);
	SetBool(RoadSourceTitle, bUseSplineRoads);
	SetVector(SizeFullTitle, FVector(Half, Half, 1.0));
	SetVector(SizeCandTitle, FVector(Half - 400.0, Half - 400.0, 1.0));
	SetVector(SizeBlockTitle, FVector(Half - 1500.0, Half - 1500.0, 1.0));
	SetDouble(SizeMaxDistTitle, Half);

	if (!bAllFound)
	{
		UE_LOG(LogPCGGame, Warning,
			TEXT("TownActor: some parameter nodes were not found in graph '%s' — is it the v5 town graph?"),
			*Graph->GetName());
	}
	return bAllFound;
}

bool ATownActor::ApplyStyleToGraph()
{
	UPCGGraph* Graph = PCGComponent ? PCGComponent->GetGraph() : nullptr;
	if (!Graph || !Style)
	{
		return false;
	}

	int32 NumUpdated = 0;
	for (UPCGNode* Node : Graph->GetNodes())
	{
		UPCGStaticMeshSpawnerSettings* Spawner = Node ? Cast<UPCGStaticMeshSpawnerSettings>(Node->GetSettings()) : nullptr;
		if (!Spawner)
		{
			continue;
		}

		// Spawner nodes are titled "Spawn <Category>" by the graph builder.
		FString Title = Node->GetAuthoredTitleName().ToString();
		FString CategoryName = Title;
		CategoryName.RemoveFromStart(TEXT("Spawn "));
		const FTownMeshCategory* Category = Style->Categories.Find(FName(*CategoryName));
		if (!Category || Category->Entries.IsEmpty())
		{
			continue;
		}

		UPCGMeshSelectorWeighted* Selector = Cast<UPCGMeshSelectorWeighted>(Spawner->MeshSelectorParameters);
		if (!Selector)
		{
			Spawner->SetMeshSelectorType(UPCGMeshSelectorWeighted::StaticClass());
			Selector = Cast<UPCGMeshSelectorWeighted>(Spawner->MeshSelectorParameters);
		}
		if (!Selector)
		{
			continue;
		}

		Selector->MeshEntries.Reset();
		for (const FTownMeshEntry& Entry : Category->Entries)
		{
			if (Entry.Mesh.IsNull())
			{
				continue;
			}
			FPCGMeshSelectorWeightedEntry& NewEntry = Selector->MeshEntries.Emplace_GetRef(Entry.Mesh, FMath::Max(1, Entry.Weight));
			(void)NewEntry;
		}
		Spawner->Modify();
#if WITH_EDITOR
		FPropertyChangedEvent Event(nullptr);
		static_cast<UObject*>(Spawner)->PostEditChangeProperty(Event);
#endif
		++NumUpdated;
	}

	UE_LOG(LogPCGGame, Verbose, TEXT("TownActor: style applied to %d spawners"), NumUpdated);
	return NumUpdated > 0;
}

void ATownActor::ScaleVolumeToTown()
{
	// Default brush is a 200 cm cube; cover the town plus vertical headroom.
	const float XY = TownHalfSize * 2.0f / 200.0f;
	SetActorScale3D(FVector(XY, XY, 4000.0f / 200.0f));
}

#if WITH_EDITOR
void ATownActor::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);

	if (!PropertyChangedEvent.Property)
	{
		return;
	}

	static const TSet<FName> TownProperties = {
		GET_MEMBER_NAME_CHECKED(ATownActor, TownHalfSize),
		GET_MEMBER_NAME_CHECKED(ATownActor, bUseSplineRoads),
		GET_MEMBER_NAME_CHECKED(ATownActor, bRenderMeshes),
		GET_MEMBER_NAME_CHECKED(ATownActor, Style),
	};
	if (TownProperties.Contains(PropertyChangedEvent.GetPropertyName()))
	{
		RegenerateTown();
	}
}
#endif
