// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class PCGGame : ModuleRules
{
	public PCGGame(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"UMG",
			"Slate",
			"PCG"
		});

		PrivateDependencyModuleNames.AddRange(new string[] { });

		PublicIncludePaths.AddRange(new string[] {
			"PCGGame",
			"PCGGame/Town",
			"PCGGame/Variant_Platforming",
			"PCGGame/Variant_Platforming/Animation",
			"PCGGame/Variant_Combat",
			"PCGGame/Variant_Combat/AI",
			"PCGGame/Variant_Combat/Animation",
			"PCGGame/Variant_Combat/Gameplay",
			"PCGGame/Variant_Combat/Interfaces",
			"PCGGame/Variant_Combat/UI",
			"PCGGame/Variant_SideScrolling",
			"PCGGame/Variant_SideScrolling/AI",
			"PCGGame/Variant_SideScrolling/Gameplay",
			"PCGGame/Variant_SideScrolling/Interfaces",
			"PCGGame/Variant_SideScrolling/UI"
		});
	}
}
