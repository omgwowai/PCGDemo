// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "TownStyleData.generated.h"

class UStaticMesh;

/** One weighted mesh option inside a category. */
USTRUCT(BlueprintType)
struct FTownMeshEntry
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style")
	TSoftObjectPtr<UStaticMesh> Mesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style", meta = (ClampMin = "1"))
	int32 Weight = 1;
};

/** All mesh options for one town category (Road, House, ...). */
USTRUCT(BlueprintType)
struct FTownMeshCategory
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style")
	TArray<FTownMeshEntry> Entries;
};

/**
 * Art-style registry for the PCG town: category name -> weighted mesh list.
 * Category names must match the town graph's spawner branches:
 * Road, CivicPlot, School, Hospital, Commercial, House, Tree, Light,
 * StreetTree, Bench, Bin, BusStop.
 * Create one asset per art style; assign it on ATownActor to re-skin the town.
 */
UCLASS(BlueprintType)
class PCGGAME_API UTownStyleData : public UDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style")
	TMap<FName, FTownMeshCategory> Categories;
};
