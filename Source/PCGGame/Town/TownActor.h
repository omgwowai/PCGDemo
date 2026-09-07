// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "PCGVolume.h"
#include "TownActor.generated.h"

class UTownStyleData;

/**
 * Place-and-tweak town generator. Drop one in a level, edit the parameters in
 * the Details panel and the PCG town graph regenerates around the actor.
 *
 * The actor pushes its parameters into the assigned PCG graph asset:
 * named CreateAttributeSet parameter nodes (MODE SWITCH / ROAD SOURCE SWITCH /
 * SIZE ...) get new values, and every StaticMeshSpawner is re-assembled from
 * the Style data asset. See Content/Python/create_town_pcg_graph_v5.py for the
 * graph these names come from.
 */
UCLASS(BlueprintType, HideCategories = (Collision, HLOD, Navigation))
class PCGGAME_API ATownActor : public APCGVolume
{
	GENERATED_BODY()

public:
	ATownActor(const FObjectInitializer& ObjectInitializer);

	/** Half extent of the town, cm. 12000 = 240 m across. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Town|Layout",
		meta = (ClampMin = "4000", ClampMax = "200000", Units = "cm"))
	float TownHalfSize = 12000.0f;

	/** Use SplineComponents of actors tagged "TownRoad" as roads instead of the procedural grid. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Town|Layout")
	bool bUseSplineRoads = false;

	/** True: spawn real meshes. False: colored debug points (fast iteration). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Town|Render")
	bool bRenderMeshes = true;

	/** Art style: which meshes each category spawns. Swap the asset to re-skin the whole town. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Town|Render")
	TObjectPtr<UTownStyleData> Style;

	/** Push parameters into the graph and regenerate now. Also runs automatically on property edits. */
	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Town")
	void RegenerateTown();

#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

private:
	/** Writes TownHalfSize/bUseSplineRoads/bRenderMeshes into the graph's named parameter nodes. */
	bool ApplyParametersToGraph();
	/** Rebuilds every spawner's weighted entries from Style. */
	bool ApplyStyleToGraph();
	void ScaleVolumeToTown();
};
