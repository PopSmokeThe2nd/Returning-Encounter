# Split map

This page describes how `main.dol` (G3BE9G) is divided into units in `config/G3BE9G/splits.txt`,
and how reliable each part is.

## Layout of `.text`

| Range | What it is | How we know |
|---|---|---|
| `0x800034A0`–`0x8017BF88` | Game code (Climax, ProDG GCC 2.95) | GCC prologues (`stwu r1` before `mflr r0`); `main` is at `0x8010A664` |
| `0x8017BF90`–`0x8017E350` | SN Systems debug monitor (hand-written assembly) | Custom `r30`/`r31` link conventions, `rfi`, self-modifying stubs |
| `0x8017E350`–`0x8017ED74` | SN Systems EXI host link (`SNInitComm`, `SNRead`, `SNDVDRead_init`, ...) | Function sizes match the same runtime in the RE4 decomp |
| `0x8017ED74`–`0x801B3FC4` | Libraries built with ProDG: SN runtime helpers and PC file I/O, fdlibm math, newlib string/stdio, libgcc 64-bit helpers, Bink video, and C++ code with vehicle settings (`MASS`, `SLIDEHANDBRAKERATE...`) | Function sizes match RE4's SN runtime, newlib and libgcc; strings for the rest. Contains 9 more static constructors. Not split yet |
| `0x801B3FC4`–`0x801E0D40` | Dolphin SDK (Sep 5 2002): PPCArch, OS, DB, MTX, DVD, VI, PAD, AI, AR, ARQ, AX, DSP, CARD, GX, EXI, SI, AMC stubs, debugger driver | Function sizes match the SDK in Metroid Prime and The Wind Waker (see "Library names" below). Not split yet |

## Game code groups

GCC 2.95 emits a source file's static constructor (`_GLOBAL_.I...`) as the file's last function,
followed by its static destructor (`_GLOBAL_.D...`) when there is one. The 108 constructors that
point into game code therefore mark 108 file ends. That gives 109 groups, and each one holds
**one or more whole source files**. Files without static constructors don't have a marker yet, so the
larger groups still need to be broken up.

The unit names (`game/group_<start>.cpp`) are placeholders. Where a file boundary inside a group is
known, the file gets its own unit: `game/NetricsaObject.cpp` ends where the memory card code starts
(`0x8010484C`). The hints below are class names or
strings referenced inside each group, to help with naming later. `tools/tu_groups.py` regenerates
this list.

| Unit | Start | Size | Hints |
|---|---|---|---|
| `game/group_800034A0.cpp` | `0x800034A0` | `0x1600` | cAnimControl |
| `game/group_80004AA0.cpp` | `0x80004AA0` | `0xF6F8` | cMinionAnimControl |
| `game/group_80014198.cpp` | `0x80014198` | `0x4EC` | no strings |
| `game/group_80014684.cpp` | `0x80014684` | `0x3254` | cDumDumLarge, cKamikazeMarine |
| `game/group_800178D8.cpp` | `0x800178D8` | `0xDF8` | Locator_Rhoof |
| `game/group_800186D0.cpp` | `0x800186D0` | `0x7AC` | no strings |
| `game/group_80018E7C.cpp` | `0x80018E7C` | `0x2860` | WarpSphere, DarkLordEnergy, DarkLordRef |
| `game/group_8001B6DC.cpp` | `0x8001B6DC` | `0x10720` | cDemonAAI, cDemonBAI, cSirianDarkLordAI |
| `game/group_8002BDFC.cpp` | `0x8002BDFC` | `0x46A0` | cTongueHarpyAI, cToothFishAI, cTweedleDumDumAI |
| `game/group_8003049C.cpp` | `0x8003049C` | `0x2744` | cOctochop, cAtlanteanAI |
| `game/group_80032BE0.cpp` | `0x80032BE0` | `0x1A18` | locator_fire, cAttackSquidAI, cBikerSquidAI |
| `game/group_800345F8.cpp` | `0x800345F8` | `0x2D2C` | Locator_eye, locator_claw, locator_claw2 |
| `game/group_80037324.cpp` | `0x80037324` | `0x6250` | cMonkeyMan |
| `game/group_8003D574.cpp` | `0x8003D574` | `0x62F4` | Shuriken, Locator_LHand, Locator_RHand |
| `game/group_80043868.cpp` | `0x80043868` | `0xA19C` | cWickerManAI |
| `game/group_8004DA04.cpp` | `0x8004DA04` | `0x5574` | cLegionnaireAntAI, cLegionnaireAntLeaderAI, cClearInternalFlag |
| `game/group_80052F78.cpp` | `0x80052F78` | `0x3E60` | Locator_muzzlepos, Cannon, Locator_muzzlepos |
| `game/group_80056DD8.cpp` | `0x80056DD8` | `0x24F4` | minigun_barrel, Locator_muzzlepos, Locator_barrel |
| `game/group_800592CC.cpp` | `0x800592CC` | `0x36D0` | Locator_muzzlepos, Locator_muzzlepos2, Locator_prong%ld |
| `game/group_8005C99C.cpp` | `0x8005C99C` | `0x3358` | Locator_muzzlepos, RocketLauncher, Locator_fuse |
| `game/group_8005FCF4.cpp` | `0x8005FCF4` | `0x12F0` | Locator_muzzlepos, WarpTorus, WarpTorus |
| `game/group_80060FE4.cpp` | `0x80060FE4` | `0x1150` | Locator_muzzlepos, Locator_shells2, Locator_shells |
| `game/group_80062134.cpp` | `0x80062134` | `0x7564` | Models/items/ordnance, antspearhead, gruntball |
| `game/group_80069698.cpp` | `0x80069698` | `0x140E0` | gruntball, watertrail02_Rb, Models/Effects |
| `game/group_8007D778.cpp` | `0x8007D778` | `0x1610` | == ModelDestruction, == ModelHolder2, TriggerOnDestructionFromDestru |
| `game/group_8007ED88.cpp` | `0x8007ED88` | `0x2360` | == MovingBrush, Triggered to move by damage, Starting to move |
| `game/group_800810E8.cpp` | `0x800810E8` | `0x614C` | == MusicChanger, TRIGGER or ACTIVATE received, Changing music stream.. |
| `game/group_80087234.cpp` | `0x80087234` | `0x449C` | CanSee called with NULL Object |
| `game/group_8008B6D0.cpp` | `0x8008B6D0` | `0x1704` | innerflash, outerflash, Could not add take damage call |
| `game/group_8008CDD4.cpp` | `0x8008CDD4` | `0xAA50` | Models/enemies, Minion_TargetTrackNextFrame() , %08x i'm going to sleep [d2=%f |
| `game/group_80097824.cpp` | `0x80097824` | `0x2F04` | cMinionStats |
| `game/group_8009A728.cpp` | `0x8009A728` | `0x21A4` | textures |
| `game/group_8009C8CC.cpp` | `0x8009C8CC` | `0x4A10` | And Die :(, Models/items, AmmoValues |
| `game/group_800A12DC.cpp` | `0x800A12DC` | `0xE15C` | textures, cTestAI, vampire |
| `game/group_800AF438.cpp` | `0x800AF438` | `0x8234` | hud_alpha, tunnel7, tunnel7 |
| `game/group_800B766C.cpp` | `0x800B766C` | `0x785C` | ------------------------------, soundid: %d, groundtype: %d |
| `game/group_800BEEC8.cpp` | `0x800BEEC8` | `0x222C` | BUMP goes the player, ms touchfield, More than %d touchfields hit i |
| `game/group_800C10F4.cpp` | `0x800C10F4` | `0x2368` | Player.ProfileTemplate, PlayerProfiles, Profile%d |
| `game/group_800C345C.cpp` | `0x800C345C` | `0x934` | no strings |
| `game/group_800C3D90.cpp` | `0x800C3D90` | `0x4BA0` | WeaponReticules, WeaponWheelDelay, Trying to add command, to full |
| `game/group_800C8930.cpp` | `0x800C8930` | `0x1110` | BODGE ALERT, Models, Models |
| `game/group_800C9A40.cpp` | `0x800C9A40` | `0xC9C` | no strings |
| `game/group_800CA6DC.cpp` | `0x800CA6DC` | `0x744` | no strings |
| `game/group_800CAE20.cpp` | `0x800CAE20` | `0x1F40` | Models/effects |
| `game/group_800CCD60.cpp` | `0x800CCD60` | `0x790` | no strings |
| `game/group_800CD4F0.cpp` | `0x800CD4F0` | `0x24EC` | SmallFlame, SmallFlameDistort, Could not allocate effect! |
| `game/group_800CF9DC.cpp` | `0x800CF9DC` | `0x11F0` | no strings |
| `game/group_800D0BCC.cpp` | `0x800D0BCC` | `0x5498` | no strings |
| `game/group_800D6064.cpp` | `0x800D6064` | `0x16B0` | no strings |
| `game/group_800D7714.cpp` | `0x800D7714` | `0x4028` | Unable to offer fire stream ha |
| `game/group_800DB73C.cpp` | `0x800DB73C` | `0x294C` | Models, SystemSetup, BloodyGibs |
| `game/group_800DE088.cpp` | `0x800DE088` | `0x163C` | Models/Effects, blast2, Textures |
| `game/group_800DF6C4.cpp` | `0x800DF6C4` | `0x1ED0` | Models/Effects, blast2, Textures |
| `game/group_800E1594.cpp` | `0x800E1594` | `0x4914` | LensFlareConfigs, NumberFlareTypes, Flare%ld |
| `game/group_800E5EA8.cpp` | `0x800E5EA8` | `0x1D74` | spawn_gradient, Trying to update disabled Smok |
| `game/group_800E7C1C.cpp` | `0x800E7C1C` | `0x2E64` | sonicelectro, sonicshellvoid, sonicringwave |
| `game/group_800EAA80.cpp` | `0x800EAA80` | `0x2E2C` | Models/Effects, blast2, Textures |
| `game/group_800ED8AC.cpp` | `0x800ED8AC` | `0x213C` | Surface type index, wrong. Val, SmallFlameDistort |
| `game/group_800EF9E8.cpp` | `0x800EF9E8` | `0x6AC` | no strings |
| `game/group_800F0094.cpp` | `0x800F0094` | `0x75C` | GuiA:ArrowL, GuiA:ArrowR |
| `game/group_800F07F0.cpp` | `0x800F07F0` | `0x28C` | no strings |
| `game/group_800F0A7C.cpp` | `0x800F0A7C` | `0x130` | no strings |
| `game/group_800F0BAC.cpp` | `0x800F0BAC` | `0x1090` | GuiA:ArrowL, GuiA:ArrowR |
| `game/group_800F1C3C.cpp` | `0x800F1C3C` | `0x270` | no strings |
| `game/group_800F1EAC.cpp` | `0x800F1EAC` | `0x5E8` | no strings |
| `game/group_800F2494.cpp` | `0x800F2494` | `0x980` | no strings |
| `game/group_800F2E14.cpp` | `0x800F2E14` | `0x4E4` | no strings |
| `game/group_800F32F8.cpp` | `0x800F32F8` | `0x68` | no strings |
| `game/group_800F3360.cpp` | `0x800F3360` | `0x68` | no strings |
| `game/group_800F33C8.cpp` | `0x800F33C8` | `0x11A0` | models |
| `game/group_800F4568.cpp` | `0x800F4568` | `0xD58` | GuiA:Arrow |
| `game/group_800F52C0.cpp` | `0x800F52C0` | `0x4A6C` | (GUI) %i Components, BackGround, GUI STILL OPEN |
| `game/group_800F9D2C.cpp` | `0x800F9D2C` | `0x1830` | Prev GUI Closing. Going to Pre |
| `game/group_800FB55C.cpp` | `0x800FB55C` | `0x988` | no strings |
| `game/group_800FBEE4.cpp` | `0x800FBEE4` | `0xC34` | Sam_FE |
| `game/group_800FCB18.cpp` | `0x800FCB18` | `0x2CC` | FrontendA, FrontEndA, Difficulty |
| `game/group_800FCDE4.cpp` | `0x800FCDE4` | `0x1DB0` | LevelGfx, hud_alpha, LevelGfx |
| `game/group_800FEB94.cpp` | `0x800FEB94` | `0x17CC` | FrontEndA, FrontEndA, GameSetup.RulesFragmatch.FragL |
| `game/group_80100360.cpp` | `0x80100360` | `0x7D0` | Level, LevelSet, Level |
| `game/group_80100B30.cpp` | `0x80100B30` | `0xDB4` | LevelGfx, GuiA:BombFEBack, GuiA:BombFEGlow |
| `game/group_801018E4.cpp` | `0x801018E4` | `0x24A0` | InitNetricsa, Netricsa, Netricsa |
| `game/NetricsaObject.cpp` | `0x80103D84` | `0xAC8` | CcNetricsaObject, CcNetricsaEnemyObject, CcNetricsaItemObject, CcNetricsaEnemyPartsObject (placeholder name); also owns `.rodata` `0x80219468`–`0x802196D8` |
| `game/group_8010484C.cpp` | `0x8010484C` | `0x32D0` | Memcard Callback Ch:%i Msg:%i |
| `game/group_80107B1C.cpp` | `0x80107B1C` | `0xBD4` | BombFE, GuiA:BombFEBack, GuiA:BombFEGlow |
| `game/group_801086F0.cpp` | `0x801086F0` | `0x338` | CheatWeapons, CheatAmmmo, CheatGOD |
| `game/group_80108A28.cpp` | `0x80108A28` | `0x15A0` | Scoring.Time, Mult, Time:   %d*%d+%d=%d |
| `game/group_80109FC8.cpp` | `0x80109FC8` | `0x69C` | %s_MODEL_NAME, Name, %s_MODEL_NAME |
| `game/group_8010A664.cpp` | `0x8010A664` | `0x4194` | STATUS: Reached Entry Point, ------------------------------, STATUS: Initialised g_system |
| `game/group_8010E7F8.cpp` | `0x8010E7F8` | `0xC3E4` | Failed to find sample in FindH, .dat, SystemSetup |
| `game/group_8011ABDC.cpp` | `0x8011ABDC` | `0x7DC4` | ------ >> IMPORT_Read_Old(%s), ------ << IMPORT_Read_Old(%s) , Loading from memory instead of |
| `game/group_801229A0.cpp` | `0x801229A0` | `0x7534` | Clip=%d FrameCount=%d, Clip does not exist!, Mesh is at %X |
| `game/group_80129ED4.cpp` | `0x80129ED4` | `0x5F3C` | %s.ssf, RES_FONT_load: Read "%s", RES_FONT_load: Read Failed |
| `game/group_8012FE10.cpp` | `0x8012FE10` | `0xD4DC` | Invalid display list data addr, Invalid display list data size, Stupid timebase on trail objec |
| `game/group_8013D2EC.cpp` | `0x8013D2EC` | `0x99B0` | NULL STRING, Object Being Completely hidden, LightDefault %d  col=<%0.2f,%0 |
| `game/group_80146C9C.cpp` | `0x80146C9C` | `0x34C4` | SetDlistVertexFormat called wi, SetVertexFormat called with Un, Vertex format incorect %d!=%d |
| `game/group_8014A160.cpp` | `0x8014A160` | `0x4178` | MATRIX %8x Error!  Failed Posi, ID'd as "%s"., C:/SeriousSam/src/game/system/ |
| `game/group_8014E2D8.cpp` | `0x8014E2D8` | `0x14C0` | !!!!!!!!!!!! Failed to find fi, Open %s, Read past fileend |
| `game/group_8014F798.cpp` | `0x8014F798` | `0x2538` | Pad %d connected, type: %s, Pad %d removed, Pad %d - PAD_ERR_NOT_READY |
| `game/group_80151CD0.cpp` | `0x80151CD0` | `0x419C` | CSceneManager |
| `game/group_80155E6C.cpp` | `0x80155E6C` | `0xD150` | Sample %d Not Loaded, Audio Interface failed to init, Could not initialize ARAM mana |
| `game/group_80162FBC.cpp` | `0x80162FBC` | `0xEE0` | ngclib_atoi cannot convert %s, ngclib_atof cannot convert %s, %s%s |
| `game/group_80163E9C.cpp` | `0x80163E9C` | `0x324` | SystemSetup.Language, SystemSetup.Language, SystemSetup.Language |
| `game/group_801641C0.cpp` | `0x801641C0` | `0xF2C` | CreditsBack, CreditsFore, Credits |
| `game/group_801650EC.cpp` | `0x801650EC` | `0x1024` | ******************************, levels, rlevel1_1 |
| `game/group_80166110.cpp` | `0x80166110` | `0x2DF8` | CScene_GameScene |
| `game/group_80168F08.cpp` | `0x80168F08` | `0xC06C` | Engine Testbed, Main Game Scene, Front-End Scene |
| `game/group_80174F74.cpp` | `0x80174F74` | `0x53C` | JeepRocketLauncher |
| `game/group_801754B0.cpp` | `0x801754B0` | `0x2060` | Models, Locator_Blade, Locator_Gibs |
| `game/group_80177510.cpp` | `0x80177510` | `0x3B14` | Models, locator_muzzlepos%ld, Locator_barrlepos%ld |
| `game/group_8017B024.cpp` | `0x8017B024` | `0xF64` | Models, SubMinigun, SubRocketLauncher |

## Next steps for finer splits

- **Data ordering.** Every section is laid out in the same link order, so each file's string literals
  and float constants in `.rodata` form one block, in file order. Where the `.rodata` that functions
  reference jumps to a new block, a file boundary is likely.
- **Debug strings.** About 90 `cClass::Method()` messages name the class a function belongs to.
- **Libraries.** Split the SDK by file using the references below, and identify Bink.

## Library names

Library functions were named by lining up their sizes with the symbol lists of other decompiled
GameCube games: Metroid Prime and The Wind Waker (same SDK revision as ours for GX), Super Mario
Sunshine, Animal Crossing, Mario Party 4 and Melee for other SDK versions, and Resident Evil 4, which
was also built with ProDG, for the SN runtime, newlib and libgcc. A name was only taken when the
neighbouring functions line up with the same reference, and when no neighbour of the same size
could be swapped in. Some short functions were checked by hand (for example `DCStoreRange` uses
`dcbst`, and `OSPanic` is called with a file name and line).

About 710 functions are named this way. Still unnamed: the AX audio library, Bink, the vehicle
code, and parts of newlib.

Two runtime functions are left unnamed on purpose: `__init_user` (0x801B9AB8) and `__init_cpp`
(0x801B9AD8). Once they're named, dtk treats the address of the constructor table as the
linker symbol `_ctors`, which mwld can't produce for this layout (the table is in `.ctors.dtors`,
not `.ctors`), and the link crashes. The stack and arena addresses OSInit uses come from
`config/G3BE9G/ldscript.tpl`, which places them where ProDG did.
