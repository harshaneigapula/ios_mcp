from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any
import os
try:
    from .database import Database
    from .device import mount_device, scan_photos, get_devices, get_device_info, unmount_device
except ImportError:
    from database import Database
    from device import mount_device, scan_photos, get_devices, get_device_info, unmount_device

# Initialize FastMCP server
mcp = FastMCP("iOS MCP Server")

# Initialize Database
db = Database()

# Configuration
MOUNT_POINT = "/tmp/iphone"

@mcp.tool()
def list_connected_devices() -> str:
    """
    List all connected iOS devices.
    """
    rc, out, err = get_devices()
    if rc != 0:
        return f"Error listing devices: {err}"
    return out

@mcp.tool()
def get_device_details(udid: str) -> str:
    """
    Get detailed info about a specific device by UDID.
    """
    rc, info, err = get_device_info(udid)
    if rc != 0:
        return f"Error getting info: {err}"
    return str(info)

@mcp.tool()
def scan_and_cache_photos() -> str:
    """
    Mounts the device, scans for photos/videos in DCIM, and caches metadata in the local database.
    Returns the number of files indexed.
    """
    # 1. Mount
    success, msg = mount_device(MOUNT_POINT)
    if not success:
        return f"Failed to mount: {msg}"
    
    # 2. Scan
    try:
        # Optimization: Fetch existing files map to skip re-scanning
        existing_files = db.get_existing_files_map()
        metadata_list = scan_photos(MOUNT_POINT, existing_files=existing_files)
    except Exception as e:
        return f"Error scanning photos: {e}"
        
    # 3. Cache
    if metadata_list:
        db.upsert_files(metadata_list)
        return f"Successfully indexed {len(metadata_list)} new files. (Skipped {len(existing_files)})"
    else:
        return f"No new files found. (Already cached {len(existing_files)})"

@mcp.tool()
def search_files(query: str, n_results: int = 10) -> str:
    """
    Search for files using natural language.
    Example: "Find photos of mountains" or "Videos from 2024"
    n_results is the number of results to return. If not needed pass None.

    IMPORTANT RESTRICTIONS:
    1. This search is based on METADATA ONLY (filenames, dates, location, camera settings, etc.).
    2. It DOES NOT analyze the visual content of images. It cannot "see" the image.
    3. Queries like "photo of a dog" will only work if "dog" is explicitly mentioned in the metadata (e.g. filename 'dog.jpg' or UserComment).
    4. Available metadata includes: EXIF (Camera, Lens, ISO), Composite (GPS, ShutterSpeed), MakerNotes, IPTC, and XMP. Call get_metadata_keys() to see all available metadata keys in DB. 
    """
    # ChromaDB handles the embedding and semantic search
    results = db.query_files(query=query, n_results=n_results)
    return str(results)

@mcp.tool()
def filter_files(criteria: str, n_results: int = 10) -> str:
    """
    Filter files by exact metadata values using MongoDB-style operators.
    Input must be a valid JSON string.
    n_results is the number of results to return. If not needed pass None.  
    Call get_metadata_keys() to see all available metadata keys in DB.

    Supported Operators:
    - Comparison: $eq (equal), $ne (not equal), $gt (greater than), $gte (greater than or equal), $lt (less than), $lte (less than or equal)
    - Inclusion: $in (in list), $nin (not in list)
    - Logical: $and, $or

    CRITICAL SYNTAX RULES:
    1. For multiple conditions, you MUST use "$and" or "$or". Implicit AND (e.g., {"Field1": "A", "Field2": "B"}) is NOT supported and will fail.
    2. Field names are case-sensitive (e.g., "EXIF:ISO", "Model").
    
    Examples:
    - Simple equality: {"Model": "iPhone 12"}
    - Comparison: {"EXIF:ISO": {"$gte": 100}}
    - Multiple conditions (REQUIRED syntax):
      {
        "$and": [
            {"EXIF:ISO": {"$gte": 100}},
            {"Model": "iPhone 12"}
        ]
      }
    - OR condition:
      {
        "$or": [
            {"Model": "iPhone 12"},
            {"Model": "iPhone 13"}
        ]
      }
    """
    import json
    try:
        where_clause = json.loads(criteria)
    except json.JSONDecodeError:
        return "Error: Criteria must be a valid JSON string."
        
    results = db.query_files(where=where_clause)
    return str(results)

@mcp.tool()
def mount_device_for_file_access():
    """
    Mount the device for file access. 
    Uses the configured mount point.
    """
    success, msg = mount_device(MOUNT_POINT)
    if not success:
        return f"Failed to mount: {msg}"
    return "Mounted successfully"

@mcp.tool()
def unmount_device_for_file_access():
    """
    Unmount the device for file access.
    """
    success, msg = unmount_device(MOUNT_POINT)
    if not success:
        return f"Failed to unmount: {msg}"
    return "Unmounted successfully"

@mcp.tool()
def get_metadata_keys() -> str:
    """
    Get a list of all available metadata keys (columns) in the database.
    Use this to understand what fields you can filter by.
    """
    keys = list(db.get_all_keys())
    keys.sort()
    return str(keys)

@mcp.tool()
def find_similar_metadata_keys(key_name: str) -> str:
    """
    Find valid metadata keys that are similar to the provided key_name.
    Use this if a filter fails or if you are unsure of the exact field name.
    """
    matches = db.find_similar_keys(key_name)
    if matches:
        return f"Did you mean one of these? {matches}"
    else:
        return "No similar keys found."

@mcp.tool()
def read_image(file_path: str) -> str:
    """
    Read an image file from the mounted device and return it as a JSON string with base64 encoded content.
    Supports standard images (JPG, PNG) and automatically converts HEIC to JPEG.
    
    IMPORTANT: Resizes the image to keep the payload small for LLM consumption.
    
    Output Format:
    {
        "type": "image",
        "data": "BASE64_STRING",
        "mimeType": "image/jpeg"
    }
    """
    import base64
    import subprocess
    import tempfile
    import json
    import mimetypes
    
    # Security check: ensure path is within mount point
    if not file_path.startswith(MOUNT_POINT):
        return "Access denied: File is outside the mount point."
        
    if not os.path.exists(file_path):
        return "File not found."
        
    try:
        # Always use a temp file for resizing
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            # Use sips to resize and convert to JPEG
            # -Z 128: Resample height and width to max 128px
            # -s format jpeg: Output as JPEG
            cmd = ["sips", "-Z", "1024", "-s", "format", "jpeg", file_path, "--out", tmp_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return f"Error processing image: {result.stderr}"
                
            with open(tmp_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            mime_type = "image/jpeg"
                
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # Construct JSON response
        response = {
            "type": "image",
            "data": encoded_string,
            "mimeType": mime_type
        }
        return json.dumps(response)
            
    except Exception as e:
        return f"Error reading image: {e}"


@mcp.tool()
def copy_files_to_local(source_paths: List[str], destination_folder: str) -> str:
    """
    Copy multiple files from the mounted device to a local destination folder.
    """
    import shutil
    
    # Ensure destination folder exists
    if not os.path.exists(destination_folder):
        try:
            os.makedirs(destination_folder, exist_ok=True)
        except Exception as e:
            return f"Error creating destination folder: {e}"
            
    success_count = 0
    errors = []
    
    for src in source_paths:
        # Security check['APP10:HDRGainCurve', 'APP10:HDRGainCurveSize', 'APP14:APP14Flags0', 'APP14:APP14Flags1', 'APP14:ColorTransform', 'APP14:DCTEncodeVersion', 'Composite:Aperture', 'Composite:AutoFocus', 'Composite:AvgBitrate', 'Composite:BlueBalance', 'Composite:CircleOfConfusion', 'Composite:ContrastDetectAF', 'Composite:DOF', 'Composite:DateTimeCreated', 'Composite:DigitalCreationDateTime', 'Composite:FOV', 'Composite:FocalLength35efl', 'Composite:GPSAltitude', 'Composite:GPSAltitudeRef', 'Composite:GPSDateTime', 'Composite:GPSLatitude', 'Composite:GPSLongitude', 'Composite:GPSPosition', 'Composite:HyperfocalDistance', 'Composite:ImageSize', 'Composite:LensID', 'Composite:LensSpec', 'Composite:LightValue', 'Composite:Megapixels', 'Composite:PhaseDetectAF', 'Composite:RedBalance', 'Composite:Rotation', 'Composite:RunTimeSincePowerUp', 'Composite:ScaleFactor35efl', 'Composite:ShutterSpeed', 'Composite:SubSecCreateDate', 'Composite:SubSecDateTimeOriginal', 'Composite:SubSecModifyDate', 'EXIF:ApertureValue', 'EXIF:Artist', 'EXIF:BitsPerSample', 'EXIF:BrightnessValue', 'EXIF:CFAPattern', 'EXIF:ColorSpace', 'EXIF:ComponentsConfiguration', 'EXIF:CompositeImage', 'EXIF:CompositeImageCount', 'EXIF:CompositeImageExposureTimes', 'EXIF:CompressedBitsPerPixel', 'EXIF:Compression', 'EXIF:Contrast', 'EXIF:Copyright', 'EXIF:CreateDate', 'EXIF:CustomRendered', 'EXIF:DateTimeOriginal', 'EXIF:DigitalZoomRatio', 'EXIF:ExifImageHeight', 'EXIF:ExifImageWidth', 'EXIF:ExifVersion', 'EXIF:ExposureCompensation', 'EXIF:ExposureMode', 'EXIF:ExposureProgram', 'EXIF:ExposureTime', 'EXIF:FNumber', 'EXIF:FileSource', 'EXIF:Flash', 'EXIF:FlashpixVersion', 'EXIF:FocalLength', 'EXIF:FocalLengthIn35mmFormat', 'EXIF:GPSAltitude', 'EXIF:GPSAltitudeRef', 'EXIF:GPSDOP', 'EXIF:GPSDateStamp', 'EXIF:GPSDestBearing', 'EXIF:GPSDestBearingRef', 'EXIF:GPSHPositioningError', 'EXIF:GPSImgDirection', 'EXIF:GPSImgDirectionRef', 'EXIF:GPSLatitude', 'EXIF:GPSLatitudeRef', 'EXIF:GPSLongitude', 'EXIF:GPSLongitudeRef', 'EXIF:GPSSpeed', 'EXIF:GPSSpeedRef', 'EXIF:GPSTimeStamp', 'EXIF:GPSVersionID', 'EXIF:GainControl', 'EXIF:HostComputer', 'EXIF:ISO', 'EXIF:ImageHeight', 'EXIF:ImageUniqueID', 'EXIF:ImageWidth', 'EXIF:InteropIndex', 'EXIF:InteropVersion', 'EXIF:LensInfo', 'EXIF:LensMake', 'EXIF:LensModel', 'EXIF:LensSerialNumber', 'EXIF:LightSource', 'EXIF:Make', 'EXIF:MeteringMode', 'EXIF:Model', 'EXIF:ModifyDate', 'EXIF:OffsetTime', 'EXIF:OffsetTimeDigitized', 'EXIF:OffsetTimeOriginal', 'EXIF:Orientation', 'EXIF:PhotometricInterpretation', 'EXIF:RecommendedExposureIndex', 'EXIF:ResolutionUnit', 'EXIF:SamplesPerPixel', 'EXIF:Saturation', 'EXIF:SceneCaptureType', 'EXIF:SceneType', 'EXIF:SensingMethod', 'EXIF:SensitivityType', 'EXIF:SerialNumber', 'EXIF:Sharpness', 'EXIF:ShutterSpeedValue', 'EXIF:Software', 'EXIF:SubSecTime', 'EXIF:SubSecTimeDigitized', 'EXIF:SubSecTimeOriginal', 'EXIF:SubjectArea', 'EXIF:SubjectDistanceRange', 'EXIF:ThumbnailImage', 'EXIF:ThumbnailLength', 'EXIF:ThumbnailOffset', 'EXIF:TileLength', 'EXIF:TileWidth', 'EXIF:UserComment', 'EXIF:WhiteBalance', 'EXIF:XResolution', 'EXIF:YCbCrPositioning', 'EXIF:YResolution', 'ExifTool:ExifToolVersion', 'ExifTool:Warning', 'File:BitsPerSample', 'File:ColorComponents', 'File:CurrentIPTCDigest', 'File:Directory', 'File:EncodingProcess', 'File:ExifByteOrder', 'File:FileAccessDate', 'File:FileInodeChangeDate', 'File:FileModifyDate', 'File:FileName', 'File:FilePermissions', 'File:FileSize', 'File:FileType', 'File:FileTypeExtension', 'File:ImageHeight', 'File:ImageWidth', 'File:MIMEType', 'File:XAttrLastUsedDate', 'File:XAttrQuarantine', 'File:YCbCrSubSampling', 'ICC_Profile:AToB0', 'ICC_Profile:BToA0', 'ICC_Profile:BlueMatrixColumn', 'ICC_Profile:BlueTRC', 'ICC_Profile:CMMFlags', 'ICC_Profile:ChromaticAdaptation', 'ICC_Profile:ColorPrimaries', 'ICC_Profile:ColorSpaceData', 'ICC_Profile:ConnectionSpaceIlluminant', 'ICC_Profile:DeviceAttributes', 'ICC_Profile:DeviceManufacturer', 'ICC_Profile:DeviceModel', 'ICC_Profile:GrayTRC', 'ICC_Profile:GreenMatrixColumn', 'ICC_Profile:GreenTRC', 'ICC_Profile:HDGainMapInfo', 'ICC_Profile:Luminance', 'ICC_Profile:MatrixCoefficients', 'ICC_Profile:MediaWhitePoint', 'ICC_Profile:PrimaryPlatform', 'ICC_Profile:ProfileCMMType', 'ICC_Profile:ProfileClass', 'ICC_Profile:ProfileConnectionSpace', 'ICC_Profile:ProfileCopyright', 'ICC_Profile:ProfileCreator', 'ICC_Profile:ProfileDateTime', 'ICC_Profile:ProfileDescription', 'ICC_Profile:ProfileDescriptionML', 'ICC_Profile:ProfileDescriptionML-ar-EG', 'ICC_Profile:ProfileDescriptionML-ca-ES', 'ICC_Profile:ProfileDescriptionML-cs-CZ', 'ICC_Profile:ProfileDescriptionML-da-DK', 'ICC_Profile:ProfileDescriptionML-de-DE', 'ICC_Profile:ProfileDescriptionML-el-GR', 'ICC_Profile:ProfileDescriptionML-es-ES', 'ICC_Profile:ProfileDescriptionML-fi-FI', 'ICC_Profile:ProfileDescriptionML-fr-FU', 'ICC_Profile:ProfileDescriptionML-he-IL', 'ICC_Profile:ProfileDescriptionML-hr-HR', 'ICC_Profile:ProfileDescriptionML-hu-HU', 'ICC_Profile:ProfileDescriptionML-it-IT', 'ICC_Profile:ProfileDescriptionML-ja-JP', 'ICC_Profile:ProfileDescriptionML-ko-KR', 'ICC_Profile:ProfileDescriptionML-nb-NO', 'ICC_Profile:ProfileDescriptionML-nl-NL', 'ICC_Profile:ProfileDescriptionML-pl-PL', 'ICC_Profile:ProfileDescriptionML-pt-BR', 'ICC_Profile:ProfileDescriptionML-pt-PO', 'ICC_Profile:ProfileDescriptionML-ro-RO', 'ICC_Profile:ProfileDescriptionML-ru-RU', 'ICC_Profile:ProfileDescriptionML-sk-SK', 'ICC_Profile:ProfileDescriptionML-sv-SE', 'ICC_Profile:ProfileDescriptionML-th-TH', 'ICC_Profile:ProfileDescriptionML-tr-TR', 'ICC_Profile:ProfileDescriptionML-uk-UA', 'ICC_Profile:ProfileDescriptionML-vi-VN', 'ICC_Profile:ProfileDescriptionML-zh-CN', 'ICC_Profile:ProfileDescriptionML-zh-TW', 'ICC_Profile:ProfileFileSignature', 'ICC_Profile:ProfileID', 'ICC_Profile:ProfileVersion', 'ICC_Profile:RedMatrixColumn', 'ICC_Profile:RedTRC', 'ICC_Profile:RenderingIntent', 'ICC_Profile:TransferCharacteristics', 'ICC_Profile:VideoFullRangeFlag', 'IPTC:ApplicationRecordVersion', 'IPTC:CodedCharacterSet', 'IPTC:DateCreated', 'IPTC:DigitalCreationDate', 'IPTC:DigitalCreationTime', 'IPTC:DocumentNotes', 'IPTC:TimeCreated', 'JFIF:JFIFVersion', 'JFIF:ResolutionUnit', 'JFIF:XResolution', 'JFIF:YResolution', 'MPF:DependentImage1EntryNumber', 'MPF:DependentImage2EntryNumber', 'MPF:MPFVersion', 'MPF:MPImage2', 'MPF:MPImage3', 'MPF:MPImageFlags', 'MPF:MPImageFormat', 'MPF:MPImageLength', 'MPF:MPImageStart', 'MPF:MPImageType', 'MPF:NumberOfImages', 'MPF:PreviewImage', 'MakerNotes:AEAverage', 'MakerNotes:AEStable', 'MakerNotes:AETarget', 'MakerNotes:AF-AssistIlluminator', 'MakerNotes:AF-CPrioritySel', 'MakerNotes:AF-OnButton', 'MakerNotes:AF-SPrioritySel', 'MakerNotes:AFActivation', 'MakerNotes:AFAreaHeight', 'MakerNotes:AFAreaMode', 'MakerNotes:AFAreaWidth', 'MakerNotes:AFAreaXPosition', 'MakerNotes:AFAreaYPosition', 'MakerNotes:AFConfidence', 'MakerNotes:AFCoordinatesAvailable', 'MakerNotes:AFDetectionMethod', 'MakerNotes:AFFineTune', 'MakerNotes:AFFineTuneAdj', 'MakerNotes:AFFineTuneAdjTele', 'MakerNotes:AFFineTuneIndex', 'MakerNotes:AFImageHeight', 'MakerNotes:AFImageWidth', 'MakerNotes:AFInfo2Version', 'MakerNotes:AFMeasuredDepth', 'MakerNotes:AFPerformance', 'MakerNotes:AFPointSel', 'MakerNotes:AFStable', 'MakerNotes:AccelerationVector', 'MakerNotes:ActiveD-Lighting', 'MakerNotes:ApertureLock', 'MakerNotes:ApplySettingsToLiveView', 'MakerNotes:AssignMovieRecordButton', 'MakerNotes:AssignMovieSubselector', 'MakerNotes:AutoBracketModeM', 'MakerNotes:AutoDistortionControl', 'MakerNotes:AutoFlashISOSensitivity', 'MakerNotes:BlockShotAFResponse', 'MakerNotes:BracketProgram', 'MakerNotes:BracketSet', 'MakerNotes:Brightness', 'MakerNotes:BurstUUID', 'MakerNotes:CLModeShootingSpeed', 'MakerNotes:CameraType', 'MakerNotes:CenterWeightedAreaSize', 'MakerNotes:Clarity', 'MakerNotes:CmdDialsChangeMainSub', 'MakerNotes:CmdDialsMenuAndPlayback', 'MakerNotes:CmdDialsReverseRotation', 'MakerNotes:ColorBalanceVersion', 'MakerNotes:ColorSpace', 'MakerNotes:ColorTemperature', 'MakerNotes:ColorTemperatureAuto', 'MakerNotes:ContentIdentifier', 'MakerNotes:ContinuousModeDisplay', 'MakerNotes:Contrast', 'MakerNotes:CropHiSpeed', 'MakerNotes:DateDisplayFormat', 'MakerNotes:DaylightSavings', 'MakerNotes:DiffractionCompensation', 'MakerNotes:DirectoryNumber', 'MakerNotes:DynamicAreaAFAssist', 'MakerNotes:EasyExposureCompensation', 'MakerNotes:EnergySavingMode', 'MakerNotes:ExposureBracketValue', 'MakerNotes:ExposureControlStepSize', 'MakerNotes:ExposureDelayMode', 'MakerNotes:ExposureDifference', 'MakerNotes:ExposureTuning', 'MakerNotes:ExtendedShutterSpeeds', 'MakerNotes:ExternalFlashExposureComp', 'MakerNotes:ExternalFlashFirmware', 'MakerNotes:ExternalFlashFlags', 'MakerNotes:FNumber', 'MakerNotes:FileInfoVersion', 'MakerNotes:FileNumber', 'MakerNotes:FileNumberSequence', 'MakerNotes:FilterEffect', 'MakerNotes:FineTuneOptCenterWeighted', 'MakerNotes:FineTuneOptHighlightWeighted', 'MakerNotes:FineTuneOptMatrixMetering', 'MakerNotes:FineTuneOptSpotMetering', 'MakerNotes:FirmwareVersion', 'MakerNotes:FirmwareVersion2', 'MakerNotes:FirmwareVersion3', 'MakerNotes:FlashColorFilter', 'MakerNotes:FlashCommanderMode', 'MakerNotes:FlashControlMode', 'MakerNotes:FlashExposureBracketValue', 'MakerNotes:FlashExposureCompArea', 'MakerNotes:FlashGNDistance', 'MakerNotes:FlashGroupAControlMode', 'MakerNotes:FlashGroupAOutput', 'MakerNotes:FlashGroupBControlMode', 'MakerNotes:FlashGroupBOutput', 'MakerNotes:FlashGroupCControlMode', 'MakerNotes:FlashGroupCOutput', 'MakerNotes:FlashIlluminationPattern', 'MakerNotes:FlashInfoVersion', 'MakerNotes:FlashMasterControlMode', 'MakerNotes:FlashMode', 'MakerNotes:FlashOutput', 'MakerNotes:FlashSetting', 'MakerNotes:FlashShutterSpeed', 'MakerNotes:FlashSource', 'MakerNotes:FlashSyncSpeed', 'MakerNotes:FlashType', 'MakerNotes:FlickAdvanceDirection', 'MakerNotes:FlickerReductionShooting', 'MakerNotes:FocalLength', 'MakerNotes:FocusDistance', 'MakerNotes:FocusDistanceRange', 'MakerNotes:FocusMode', 'MakerNotes:FocusPeakingHighlightColor', 'MakerNotes:FocusPeakingLevel', 'MakerNotes:FocusPointSchema', 'MakerNotes:FocusPointWrap', 'MakerNotes:FocusPosition', 'MakerNotes:FocusPositionHorizontal', 'MakerNotes:FocusPositionVertical', 'MakerNotes:FocusShiftExposureLock', 'MakerNotes:FocusShiftInterval', 'MakerNotes:FocusShiftNumberShots', 'MakerNotes:FocusShiftStepWidth', 'MakerNotes:FramingGridDisplay', 'MakerNotes:Func1Button', 'MakerNotes:Func2Button', 'MakerNotes:HDMIBitDepth', 'MakerNotes:HDMIExternalRecorder', 'MakerNotes:HDMIOutputRange', 'MakerNotes:HDMIOutputResolution', 'MakerNotes:HDR', 'MakerNotes:HDRGain', 'MakerNotes:HDRHeadroom', 'MakerNotes:HDRInfoVersion', 'MakerNotes:HDRLevel', 'MakerNotes:HDRLevel2', 'MakerNotes:HDRSmoothing', 'MakerNotes:HighISONoiseReduction', 'MakerNotes:Hue', 'MakerNotes:ISO', 'MakerNotes:ISO2', 'MakerNotes:ISOAutoFlashLimit', 'MakerNotes:ISOAutoHiLimit', 'MakerNotes:ISOAutoShutterTime', 'MakerNotes:ISOExpansion', 'MakerNotes:ISOExpansion2', 'MakerNotes:ImageArea', 'MakerNotes:ImageBoundary', 'MakerNotes:ImageCaptureType', 'MakerNotes:ImageDataSize', 'MakerNotes:ImageReviewMonitorOffTime', 'MakerNotes:ImageSizeRAW', 'MakerNotes:IntervalDurationHours', 'MakerNotes:IntervalDurationMinutes', 'MakerNotes:IntervalDurationSeconds', 'MakerNotes:IntervalExposureSmoothing', 'MakerNotes:IntervalPriority', 'MakerNotes:IntervalShooting', 'MakerNotes:Intervals', 'MakerNotes:JPGCompression', 'MakerNotes:Language', 'MakerNotes:Lens', 'MakerNotes:LensControlRing', 'MakerNotes:LensDataVersion', 'MakerNotes:LensFStops', 'MakerNotes:LensFirmwareVersion', 'MakerNotes:LensFunc1Button', 'MakerNotes:LensFunc2Button', 'MakerNotes:LensID', 'MakerNotes:LensMountType', 'MakerNotes:LensPositionAbsolute', 'MakerNotes:LensType', 'MakerNotes:LivePhotoVideoIndex', 'MakerNotes:LowLightAF', 'MakerNotes:LuminanceNoiseAmplitude', 'MakerNotes:MakerNoteVersion', 'MakerNotes:ManualFocusPointIllumination', 'MakerNotes:ManualFocusRingInAFMode', 'MakerNotes:MaxAperture', 'MakerNotes:MaxContinuousRelease', 'MakerNotes:MechanicalShutterCount', 'MakerNotes:MemoryCardNumber', 'MakerNotes:MenuMonitorOffTime', 'MakerNotes:MidRangeSharpness', 'MakerNotes:ModelingFlash', 'MakerNotes:MonitorBrightness', 'MakerNotes:MovieAF-OnButton', 'MakerNotes:MovieAFAreaMode', 'MakerNotes:MovieAFSpeed', 'MakerNotes:MovieAFSpeedApply', 'MakerNotes:MovieAFTrackingSensitivity', 'MakerNotes:MovieFunc1Button', 'MakerNotes:MovieFunc2Button', 'MakerNotes:MovieHighlightDisplayPattern', 'MakerNotes:MovieHighlightDisplayThreshold', 'MakerNotes:MovieISOAutoControlManualMode', 'MakerNotes:MovieISOAutoHiLimit', 'MakerNotes:MovieMultiSelector', 'MakerNotes:MovieShutterButton', 'MakerNotes:MovieWhiteBalanceSameAsPhoto', 'MakerNotes:MultiExposureMode', 'MakerNotes:MultiExposureOverlayMode', 'MakerNotes:MultiExposureShots', 'MakerNotes:MultiExposureVersion', 'MakerNotes:MultiSelectorPlaybackMode', 'MakerNotes:MultiSelectorShootMode', 'MakerNotes:NikonMeteringMode', 'MakerNotes:NoiseReduction', 'MakerNotes:NumberOffsets', 'MakerNotes:OISMode', 'MakerNotes:PhotoIdentifier', 'MakerNotes:PhotosAppFeatureFlags', 'MakerNotes:PictureControlAdjust', 'MakerNotes:PictureControlBase', 'MakerNotes:PictureControlName', 'MakerNotes:PictureControlQuickAdjust', 'MakerNotes:PictureControlVersion', 'MakerNotes:PitchAngle', 'MakerNotes:PlaybackMonitorOffTime', 'MakerNotes:PortraitImpressionBalance', 'MakerNotes:PowerUpTime', 'MakerNotes:PrimarySlot', 'MakerNotes:ProgramShift', 'MakerNotes:Quality', 'MakerNotes:ReleaseButtonToUseDial', 'MakerNotes:ReleaseMode', 'MakerNotes:RemoteFuncButton', 'MakerNotes:RetouchHistory', 'MakerNotes:RetouchInfoVersion', 'MakerNotes:RetouchNEFProcessing', 'MakerNotes:ReverseFocusRing', 'MakerNotes:ReverseIndicators', 'MakerNotes:RollAngle', 'MakerNotes:RunTimeEpoch', 'MakerNotes:RunTimeFlags', 'MakerNotes:RunTimeScale', 'MakerNotes:RunTimeValue', 'MakerNotes:Saturation', 'MakerNotes:SaveFocus', 'MakerNotes:SecondarySlotFunction', 'MakerNotes:SelfTimerShotCount', 'MakerNotes:SelfTimerShotInterval', 'MakerNotes:SelfTimerTime', 'MakerNotes:SemanticStyle', 'MakerNotes:SemanticStyleRenderingVer', 'MakerNotes:SerialNumber', 'MakerNotes:Sharpness', 'MakerNotes:ShootingInfoDisplay', 'MakerNotes:ShootingMode', 'MakerNotes:ShotInfoVersion', 'MakerNotes:ShotsPerInterval', 'MakerNotes:ShutterCount', 'MakerNotes:ShutterMode', 'MakerNotes:ShutterReleaseButtonAE-L', 'MakerNotes:ShutterSpeedLock', 'MakerNotes:ShutterType', 'MakerNotes:SignalToNoiseRatio', 'MakerNotes:SilentPhotography', 'MakerNotes:SingleFrame', 'MakerNotes:StandbyMonitorOffTime', 'MakerNotes:StoreByOrientation', 'MakerNotes:SubDialFrameAdvance', 'MakerNotes:SubSelector', 'MakerNotes:SubSelectorCenter', 'MakerNotes:SyncReleaseMode', 'MakerNotes:TimeZone', 'MakerNotes:ToningEffect', 'MakerNotes:ToningSaturation', 'MakerNotes:USBPowerDelivery', 'MakerNotes:VRInfoVersion', 'MakerNotes:VRMode', 'MakerNotes:VRType', 'MakerNotes:VariProgram', 'MakerNotes:VerticalAFOnButton', 'MakerNotes:VerticalFuncButton', 'MakerNotes:VerticalMovieAFOnButton', 'MakerNotes:VerticalMovieFuncButton', 'MakerNotes:VerticalMultiSelector', 'MakerNotes:VibrationReduction', 'MakerNotes:VignetteControl', 'MakerNotes:WB_RBLevels', 'MakerNotes:WhiteBalance', 'MakerNotes:WhiteBalanceFineTune', 'MakerNotes:YawAngle', 'PNG:BitDepth', 'PNG:ColorType', 'PNG:Compression', 'PNG:Filter', 'PNG:ImageHeight', 'PNG:ImageWidth', 'PNG:Interlace', 'PNG:ProfileName', 'Photoshop:CopyrightFlag', 'Photoshop:DisplayedUnitsX', 'Photoshop:DisplayedUnitsY', 'Photoshop:GlobalAltitude', 'Photoshop:GlobalAngle', 'Photoshop:HasRealMergedData', 'Photoshop:IPTCDigest', 'Photoshop:NumSlices', 'Photoshop:PhotoshopFormat', 'Photoshop:PhotoshopQuality', 'Photoshop:PhotoshopThumbnail', 'Photoshop:PixelAspectRatio', 'Photoshop:PrintPosition', 'Photoshop:PrintScale', 'Photoshop:PrintStyle', 'Photoshop:ProgressiveScans', 'Photoshop:ReaderName', 'Photoshop:SlicesGroupName', 'Photoshop:URL_List', 'Photoshop:WriterName', 'Photoshop:XResolution', 'Photoshop:YResolution', 'QuickTime:Apple-maker-note74', 'QuickTime:Apple-maker-note97', 'QuickTime:AudioBitsPerSample', 'QuickTime:AudioChannels', 'QuickTime:AudioFormat', 'QuickTime:AudioSampleRate', 'QuickTime:AuxiliaryImageType', 'QuickTime:AverageFrameRate', 'QuickTime:Balance', 'QuickTime:BitDepth', 'QuickTime:BitDepthChroma', 'QuickTime:BitDepthLuma', 'QuickTime:CameraLensIrisfnumber', 'QuickTime:CameraLensIrisfnumber-eng-US', 'QuickTime:ChromaFormat', 'QuickTime:CleanAperture', 'QuickTime:CleanApertureDimensions', 'QuickTime:ColorPrimaries', 'QuickTime:ColorProfiles', 'QuickTime:Comment', 'QuickTime:CompatibleBrands', 'QuickTime:CompressorID', 'QuickTime:CompressorName', 'QuickTime:ConstantFrameRate', 'QuickTime:ConstraintIndicatorFlags', 'QuickTime:ContentDescribes', 'QuickTime:ContentIdentifier', 'QuickTime:CreateDate', 'QuickTime:CreationDate', 'QuickTime:CurrentTime', 'QuickTime:Duration', 'QuickTime:EncodedPixelsDimensions', 'QuickTime:Encoder', 'QuickTime:FocalLengthIn35mmFormat', 'QuickTime:FocalLengthIn35mmFormat-eng-IN', 'QuickTime:FocalLengthIn35mmFormat-eng-US', 'QuickTime:FullFrameRatePlaybackIntent', 'QuickTime:GPSCoordinates', 'QuickTime:GenBalance', 'QuickTime:GenFlags', 'QuickTime:GenGraphicsMode', 'QuickTime:GenMediaVersion', 'QuickTime:GenOpColor', 'QuickTime:GenProfileCompatibilityFlags', 'QuickTime:GeneralLevelIDC', 'QuickTime:GeneralProfileIDC', 'QuickTime:GeneralProfileSpace', 'QuickTime:GeneralTierFlag', 'QuickTime:GraphicsMode', 'QuickTime:HEVCConfigurationVersion', 'QuickTime:HandlerClass', 'QuickTime:HandlerDescription', 'QuickTime:HandlerType', 'QuickTime:HandlerVendorID', 'QuickTime:ImageHeight', 'QuickTime:ImagePixelDepth', 'QuickTime:ImageSpatialExtent', 'QuickTime:ImageWidth', 'QuickTime:Keywords', 'QuickTime:LensModel', 'QuickTime:LensModel-eng-IN', 'QuickTime:LensModel-eng-US', 'QuickTime:Live-photoSubject-relighting-applied-curve-parameter', 'QuickTime:LivePhotoAuto', 'QuickTime:LivePhotoVitalityScore', 'QuickTime:LivePhotoVitalityScoringVersion', 'QuickTime:LocationAccuracyHorizontal', 'QuickTime:MajorBrand', 'QuickTime:Make', 'QuickTime:MatrixCoefficients', 'QuickTime:MatrixStructure', 'QuickTime:MaxContentLightLevel', 'QuickTime:MaxPicAverageLightLevel', 'QuickTime:MediaCreateDate', 'QuickTime:MediaDataOffset', 'QuickTime:MediaDataSize', 'QuickTime:MediaDuration', 'QuickTime:MediaHeaderVersion', 'QuickTime:MediaLanguageCode', 'QuickTime:MediaModifyDate', 'QuickTime:MediaTimeScale', 'QuickTime:MetaFormat', 'QuickTime:MetaImageSize', 'QuickTime:MinSpatialSegmentationIDC', 'QuickTime:MinorVersion', 'QuickTime:Model', 'QuickTime:ModifyDate', 'QuickTime:MovieHeaderVersion', 'QuickTime:NextTrackID', 'QuickTime:NumTemporalLayers', 'QuickTime:OpColor', 'QuickTime:ParallelismType', 'QuickTime:PosterTime', 'QuickTime:PreferredRate', 'QuickTime:PreferredVolume', 'QuickTime:PreviewDuration', 'QuickTime:PreviewTime', 'QuickTime:PrimaryItemReference', 'QuickTime:ProductionApertureDimensions', 'QuickTime:PurchaseFileFormat', 'QuickTime:Rotation', 'QuickTime:SelectionDuration', 'QuickTime:SelectionTime', 'QuickTime:Software', 'QuickTime:SourceImageHeight', 'QuickTime:SourceImageWidth', 'QuickTime:TemporalIDNested', 'QuickTime:TimeScale', 'QuickTime:TrackCreateDate', 'QuickTime:TrackDuration', 'QuickTime:TrackHeaderVersion', 'QuickTime:TrackID', 'QuickTime:TrackLayer', 'QuickTime:TrackModifyDate', 'QuickTime:TrackVolume', 'QuickTime:TransferCharacteristics', 'QuickTime:VideoFrameRate', 'QuickTime:VideoFullRangeFlag', 'QuickTime:XResolution', 'QuickTime:YResolution', 'SourceFile', 'XMP:Accuracy', 'XMP:AdsCreated', 'XMP:AdsExtId', 'XMP:AdsFbId', 'XMP:AdsTouchType', 'XMP:Author', 'XMP:AuxiliaryImageSubType', 'XMP:AuxiliaryImageType', 'XMP:CaptureMode', 'XMP:ColorMode', 'XMP:CreateDate', 'XMP:Creator', 'XMP:CreatorTool', 'XMP:DateCreated', 'XMP:DepthDataVersion', 'XMP:DerivedFrom', 'XMP:DerivedFromDocumentID', 'XMP:DerivedFromInstanceID', 'XMP:DerivedFromOriginalDocumentID', 'XMP:DocumentID', 'XMP:EffectStrength', 'XMP:ExtrinsicMatrix', 'XMP:Filtered', 'XMP:FloatMaxValue', 'XMP:FloatMinValue', 'XMP:Format', 'XMP:HDRGainMapHeadroom', 'XMP:HDRGainMapVersion', 'XMP:HistoryAction', 'XMP:HistoryChanged', 'XMP:HistoryInstanceID', 'XMP:HistoryParameters', 'XMP:HistorySoftwareAgent', 'XMP:HistoryWhen', 'XMP:ImageNumber', 'XMP:InstanceID', 'XMP:IntMaxValue', 'XMP:IntMinValue', 'XMP:IntrinsicMatrix', 'XMP:IntrinsicMatrixReferenceHeight', 'XMP:IntrinsicMatrixReferenceWidth', 'XMP:InverseLensDistortionCoefficients', 'XMP:IsHDRActive', 'XMP:IsNightModeActive', 'XMP:LegacyIPTCDigest', 'XMP:Lens', 'XMP:LensDistortionCenterOffsetX', 'XMP:LensDistortionCenterOffsetY', 'XMP:LensDistortionCoefficients', 'XMP:LensFacing', 'XMP:LensInfo', 'XMP:Marked', 'XMP:MetadataDate', 'XMP:ModifyDate', 'XMP:NativeFormat', 'XMP:OriginalDocumentID', 'XMP:PixelSize', 'XMP:PortraitEffectsMatteVersion', 'XMP:PortraitScore', 'XMP:PortraitScoreIsHigh', 'XMP:Producer', 'XMP:Quality', 'XMP:Rating', 'XMP:RegionAppliedToDimensionsH', 'XMP:RegionAppliedToDimensionsUnit', 'XMP:RegionAppliedToDimensionsW', 'XMP:RegionAreaH', 'XMP:RegionAreaUnit', 'XMP:RegionAreaW', 'XMP:RegionAreaX', 'XMP:RegionAreaY', 'XMP:RegionExtensions', 'XMP:RegionExtensionsAngleInfoRoll', 'XMP:RegionExtensionsAngleInfoYaw', 'XMP:RegionExtensionsConfidenceLevel', 'XMP:RegionExtensionsFaceID', 'XMP:RegionType', 'XMP:RenderingParameters', 'XMP:Rights', 'XMP:Scene', 'XMP:SemanticSegmentationMatteVersion', 'XMP:SerialNumber', 'XMP:SimulatedAperture', 'XMP:StoredFormat', 'XMP:Title', 'XMP:UserComment', 'XMP:XMPToolkit']
        if not src.startswith(MOUNT_POINT):
            errors.append(f"{src}: Access denied (outside mount point)")
            continue
            
        if not os.path.exists(src):
            errors.append(f"{src}: File not found")
            continue
            
        try:
            # Construct destination path (preserve filename)
            filename = os.path.basename(src)
            dest_path = os.path.join(destination_folder, filename)
            
            shutil.copy2(src, dest_path)
            success_count += 1
        except Exception as e:
            errors.append(f"{src}: {str(e)}")
            
    if not errors:
        return f"Successfully copied all {success_count} files to {destination_folder}"
    else:
        error_msg = "\n".join(errors)
        return f"Copied {success_count}/{len(source_paths)} files.\nErrors:\n{error_msg}"


@mcp.tool()
def check_db_status() -> str:
    """
    Check the status of the database connection.
    Returns "Connected" if successful, or an error message.
    """
    try:
        if db.check_connection():
            return "Connected"
        else:
            return "Disconnected: Health check failed."
    except Exception as e:
        return f"Disconnected: {e}"

@mcp.tool()
def check_mount_status() -> str:
    """
    Check the status of the file system mount point.
    Returns "Mounted" if successful, "Not Mounted" if not, or an error message.
    """
    try:
        if os.path.ismount(MOUNT_POINT):
            # Additional check: try to list directory to ensure it's readable
            try:
                os.listdir(MOUNT_POINT)
                return "Mounted and Readable"
            except PermissionError:
                return "Mounted but Permission Denied"
            except OSError as e:
                return f"Mounted but Error Accessing: {e}"
        else:
            if os.path.exists(MOUNT_POINT):
                return "Not Mounted (Directory exists)"
            else:
                return "Not Mounted (Directory does not exist)"
    except Exception as e:
        return f"Error checking mount status: {e}"

@mcp.tool()
def count_files(criteria: str = None) -> str:
    """
    Count files matching the criteria.
    Input can be a JSON string with "query" (semantic) and/or "where" (filter).
    Or just a simple string for semantic search if it's not valid JSON.
    
    Examples:
    - "mountains" (Semantic count)
    - {"Model": "iPhone 12"} (Exact filter count)
    - {"query": "mountains", "where": {"Model": "iPhone 12"}} (Combined)

    NOTE: Semantic count ("query") is based on METADATA similarity, not visual content.
    """
    import json
    query = None
    where = None
    
    if criteria:
        try:
            data = json.loads(criteria)
            if isinstance(data, dict):
                query = data.get("query")
                where = data.get("where")
                # If neither query nor where are keys, assume the whole dict is a filter
                if query is None and where is None:
                    where = data
            else:
                # If JSON but not dict (e.g. list), treat as query string
                query = str(data)
        except json.JSONDecodeError:
            # Not JSON, treat as semantic query
            query = criteria
            
    count = db.count_files(query=query, where=where)
    return str(count)

@mcp.tool()
def group_files(field: str, criteria: str = None) -> str:
    """
    Group files by a metadata field and return counts.
    Useful for getting a breakdown of files (e.g. by 'Model', 'CreationDate', 'Extension').
    
    Args:
        field: The metadata field to group by (e.g. "Model", "ext").
        criteria: Optional JSON string for filtering before grouping.
    """
    import json
    query = None
    where = None
    
    if criteria:
        try:
            data = json.loads(criteria)
            if isinstance(data, dict):
                query = data.get("query")
                where = data.get("where")
                if query is None and where is None:
                    where = data
            else:
                query = str(data)
        except json.JSONDecodeError:
            query = criteria
            
    groups = db.group_files_by_field(field=field, query=query, where=where)
    return str(groups)

@mcp.tool()
def get_database_summary() -> str:
    """
    Get a summary of the database statistics (total files, etc).
    """
    stats = db.get_database_stats()
    return str(stats)


@mcp.tool()
def run_advanced_query(criteria: str) -> str:
    """
    Run a complex query on the file database with support for filtering, semantic search, sorting, pagination, and projection.
    
    Args:
        criteria: A JSON string containing the query parameters.
    
    JSON Structure:
    {
        "query": "semantic search text" (Optional),
        "where": { ... } (Optional, Chroma/MongoDB style filter),
        "sort_by": "MetadataField" (Optional, e.g. "CreationDate", "Size"),
        "sort_order": "asc" or "desc" (Optional, default "asc"),
        "limit": 10 (Optional, default 10),
        "offset": 0 (Optional, default 0),
        "projection": ["Field1", "Field2"] (Optional, list of fields to return)
    }

    IMPORTANT: "query" uses semantic search on METADATA ONLY. It cannot find objects inside images unless they are described in the metadata.

    Examples:
    1. Find photos of mountains, sorted by date (newest first):
       {
         "query": "photos of mountains",
         "sort_by": "CreationDate",
         "sort_order": "desc"
       }
       
    2. Find all iPhone 12 photos, return only path and date:
       {
         "where": {"Model": "iPhone 12"},
         "projection": ["CreationDate"]
       }
       
    3. Pagination (Get page 2, 20 items per page):
       {
         "where": {"Model": "iPhone 12"},
         "limit": 20,
         "offset": 20
       }
    """
    import json
    try:
        data = json.loads(criteria)
    except json.JSONDecodeError:
        return "Error: Input must be a valid JSON string."
        
    if not isinstance(data, dict):
        return "Error: Input must be a JSON object."
        
    try:
        results = db.advanced_query(
            query=data.get("query"),
            where=data.get("where"),
            sort_by=data.get("sort_by"),
            sort_order=data.get("sort_order", "asc"),
            limit=data.get("limit", 10),
            offset=data.get("offset", 0),
            projection=data.get("projection")
        )
        return str(results)
    except Exception as e:
        return f"Error executing query: {e}"


@mcp.tool()
def run_aggregation_pipeline(pipeline: str) -> str:
    """
    Run a multi-stage aggregation pipeline for complex data processing.
    Modeled after MongoDB's aggregation framework.
    
    Args:
        pipeline: A JSON string representing a list of pipeline stages.
        
    Supported Stages & Syntax:
    
    1. **$match**: Filters documents (like SQL WHERE).
       - Syntax: `{"$match": { "Field": "Value", "Field2": { "$gt": 10 } }}`
       - Operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$and`, `$or`.
       - Special: Use `{"query": "search text"}` for semantic search.
       
    2. **$group**: Groups documents by `_id` and calculates accumulators.
       - Syntax: `{"$group": { "_id": "$FieldToGroupBy", "new_field": { "$accumulator": "$FieldToAccumulate" } }}`
       - Use `_id: null` to calculate stats for the entire dataset.
       - Accumulators: 
         - `$sum`: Sums values (use 1 to count).
         - `$avg`: Averages values.
         - `$min` / `$max`: Finds min/max values.
         - `$push`: Creates a list of values.
         - `$first`: Takes the first value (useful after sorting).
         
    3. **$project**: Reshapes documents (like SQL SELECT).
       - Use to keep only specific fields, rename fields, or remove fields.
       - Syntax (Inclusion): `{"$project": { "KeepField": 1, "RenameField": "$OldName" }}`
       - Syntax (Exclusion): `{"$project": { "RemoveField": 0 }}`
       
    4. **$sort**: Sorts documents (like SQL ORDER BY).
       - Syntax: `{"$sort": { "Field": 1 }}` (1 for Ascending, -1 for Descending).
       
    5. **$limit** / **$skip**: Pagination.
       - Syntax: `{"$limit": 10}`, `{"$skip": 5}`.
       
    6. **$count**: Counts results and outputs a single document.
       - Syntax: `{"$count": "output_field_name"}`.
    
    Examples:
    
    **Example 1: Filter and Count**
    "Count how many Apple devices have ISO > 100"
    ```json
    [
      {"$match": {"Make": "Apple", "ISO": {"$gt": 100}}},
      {"$count": "total_high_iso_apple"}
    ]
    ```
       
    **Example 2: Grouping and Statistics**
    "Get average ISO and total count for each Camera Model"
    ```json
    [
      {"$group": {
        "_id": "$Model", 
        "avg_iso": {"$avg": "$ISO"},
        "total": {"$sum": 1}
      }}
    ]
    ```
       
    **Example 3: Complex Pipeline (Filter -> Group -> Filter Groups -> Sort -> Project)**
    "Find models with avg ISO > 200, sort by count desc, and show only Model and Count"
    ```json
    [
      {"$match": {"Make": "Apple"}},
      {"$group": {
        "_id": "$Model", 
        "avg_iso": {"$avg": "$ISO"},
        "count": {"$sum": 1}
      }},
      {"$match": {"avg_iso": {"$gt": 200}}},
      {"$sort": {"count": -1}},
      {"$project": {"Model": "$_id", "count": 1, "_id": 0}}
    ]
    ```
    """
    import json
    try:
        pipeline_data = json.loads(pipeline)
    except json.JSONDecodeError:
        return "Error: Pipeline must be a valid JSON string."
        
    if not isinstance(pipeline_data, list):
        return "Error: Pipeline must be a list of stages."
        
    try:
        results = db.aggregate(pipeline_data)
        return str(results)
    except Exception as e:
        return f"Error executing pipeline: {e}"


if __name__ == "__main__":
    mcp.run()
