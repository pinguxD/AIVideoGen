-- AIVideoGen Roblox Studio Plugin Bridge v1
-- Install this Script as a local Studio plugin.
-- Keep the Python Flask app running at http://127.0.0.1:5000.

local HttpService = game:GetService("HttpService")
local ScriptEditorService = game:GetService("ScriptEditorService")
local StarterPlayer = game:GetService("StarterPlayer")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local Selection = game:GetService("Selection")

local BASE_URL = "http://127.0.0.1:5000"

local toolbar = plugin:CreateToolbar("AIVideoGen")
local fetchButton = toolbar:CreateButton(
    "FetchBuild",
    "Fetch the next AIVideoGen scene and build it in this place",
    "rbxassetid://4458901886",
    "Fetch & Build"
)

local widgetInfo = DockWidgetPluginGuiInfo.new(
    Enum.InitialDockState.Left,
    true,
    false,
    360,
    420,
    280,
    250
)

local widget = plugin:CreateDockWidgetPluginGui(
    "AIVideoGenBridgeWidget",
    widgetInfo
)
widget.Title = "AIVideoGen Bridge"

local root = Instance.new("Frame")
root.BackgroundColor3 = Color3.fromRGB(28, 32, 42)
root.Size = UDim2.fromScale(1, 1)
root.Parent = widget

local title = Instance.new("TextLabel")
title.BackgroundTransparency = 1
title.Text = "AIVideoGen Studio Bridge"
title.TextColor3 = Color3.fromRGB(255, 255, 255)
title.Font = Enum.Font.GothamBold
title.TextSize = 18
title.Size = UDim2.new(1, -20, 0, 42)
title.Position = UDim2.fromOffset(10, 8)
title.Parent = root

local status = Instance.new("TextLabel")
status.BackgroundColor3 = Color3.fromRGB(17, 20, 28)
status.TextColor3 = Color3.fromRGB(220, 225, 235)
status.TextWrapped = true
status.TextXAlignment = Enum.TextXAlignment.Left
status.TextYAlignment = Enum.TextYAlignment.Top
status.Font = Enum.Font.Code
status.TextSize = 14
status.Text = "Ready. Queue a job in the web app, then click Fetch & Build."
status.Size = UDim2.new(1, -20, 1, -120)
status.Position = UDim2.fromOffset(10, 54)
status.Parent = root

local fetchGuiButton = Instance.new("TextButton")
fetchGuiButton.BackgroundColor3 = Color3.fromRGB(58, 93, 140)
fetchGuiButton.TextColor3 = Color3.fromRGB(255, 255, 255)
fetchGuiButton.Font = Enum.Font.GothamBold
fetchGuiButton.TextSize = 15
fetchGuiButton.Text = "Fetch & Build"
fetchGuiButton.Size = UDim2.new(1, -20, 0, 42)
fetchGuiButton.Position = UDim2.new(0, 10, 1, -54)
fetchGuiButton.Parent = root

local busy = false

local function setStatus(text)
    status.Text = text
    print("[AIVideoGen] " .. text)
end

local function request(options)
    local ok, response = pcall(function()
        return HttpService:RequestAsync(options)
    end)
    if not ok then
        error(response)
    end
    if not response.Success then
        error(
            "HTTP " .. tostring(response.StatusCode)
            .. ": " .. tostring(response.Body)
        )
    end
    return response
end

local function postStatus(jobId, endpoint, message)
    request({
        Url = BASE_URL
            .. "/api/roblox-plugin/jobs/"
            .. HttpService:UrlEncode(jobId)
            .. "/"
            .. endpoint,
        Method = "POST",
        Headers = {
            ["Content-Type"] = "application/json",
        },
        Body = HttpService:JSONEncode({
            message = message,
        }),
    })
end

local function createPart(properties, parent)
    local part = Instance.new("Part")
    part.Name = properties.name or "GeneratedPart"
    part.Anchored = properties.anchored ~= false

    if properties.size then
        part.Size = Vector3.new(
            properties.size[1] or 4,
            properties.size[2] or 1,
            properties.size[3] or 4
        )
    end

    if properties.position then
        part.Position = Vector3.new(
            properties.position[1] or 0,
            properties.position[2] or 0,
            properties.position[3] or 0
        )
    end

    part.Parent = parent
    return part
end

local function buildEnvironment(spec, packageFolder)
    local generated = workspace:FindFirstChild("AIVideoGenGenerated")
    if generated then
        generated:Destroy()
    end

    generated = Instance.new("Folder")
    generated.Name = "AIVideoGenGenerated"
    generated.Parent = workspace

    local environment = spec.environment or {}
    local template = environment.template or "simple_platform"

    if template == "hospital_template" then
        local floor = createPart({
            name = "HospitalFloor",
            size = {48, 1, 48},
            position = {0, 0, 0},
        }, generated)

        local backWall = createPart({
            name = "HospitalBackWall",
            size = {48, 16, 1},
            position = {0, 8, 24},
        }, generated)

        floor.Color = Color3.fromRGB(222, 228, 235)
        backWall.Color = Color3.fromRGB(180, 205, 225)
    elseif template == "simple_obby" then
        for index = 1, 8 do
            local platform = createPart({
                name = "ObbyPlatform" .. index,
                size = {8, 1, 8},
                position = {(index - 1) * 10, index % 2 * 3, 0},
            }, generated)
            platform.Color = Color3.fromHSV(index / 8, 0.65, 1)
        end
    else
        local ground = createPart({
            name = "GeneratedGround",
            size = {40, 1, 40},
            position = {0, 0, 0},
        }, generated)
        ground.Color = Color3.fromRGB(214, 214, 214)
    end

    local marker = Instance.new("StringValue")
    marker.Name = "EnvironmentTemplate"
    marker.Value = template
    marker.Parent = packageFolder
end

local function buildGui(spec)
    local starterGui = game:GetService("StarterGui")
    local old = starterGui:FindFirstChild("AIVideoGenGui")
    if old then
        old:Destroy()
    end

    local guiItems = spec.gui or {}
    if #guiItems == 0 then
        return
    end

    local screenGui = Instance.new("ScreenGui")
    screenGui.Name = "AIVideoGenGui"
    screenGui.ResetOnSpawn = false
    screenGui.Parent = starterGui

    for index, item in ipairs(guiItems) do
        if item.type == "slider" then
            local frame = Instance.new("Frame")
            frame.Name = item.name or ("Slider" .. index)
            frame.Size = UDim2.fromOffset(260, 70)
            frame.Position = UDim2.new(0, 30, 0.5, -35)
            frame.BackgroundColor3 = Color3.fromRGB(26, 28, 35)
            frame.Parent = screenGui

            local label = Instance.new("TextLabel")
            label.BackgroundTransparency = 1
            label.Text = tostring(item.label or "Size")
                .. ": "
                .. tostring(item.value or 1)
            label.TextColor3 = Color3.new(1, 1, 1)
            label.Font = Enum.Font.GothamBold
            label.TextSize = 20
            label.Size = UDim2.new(1, -20, 0, 30)
            label.Position = UDim2.fromOffset(10, 4)
            label.Parent = frame

            local bar = Instance.new("Frame")
            bar.BackgroundColor3 = Color3.fromRGB(235, 235, 235)
            bar.Size = UDim2.new(1, -24, 0, 12)
            bar.Position = UDim2.fromOffset(12, 44)
            bar.Parent = frame
        end
    end
end

local function importController(generatedLua)
    local scriptsFolder = StarterPlayer:WaitForChild(
        "StarterPlayerScripts"
    )

    local existing = scriptsFolder:FindFirstChild("GeneratedScene")
    if existing then
        existing:Destroy()
    end

    local localScript = Instance.new("LocalScript")
    localScript.Name = "GeneratedScene"
    localScript.Parent = scriptsFolder

    ScriptEditorService:UpdateSourceAsync(
        localScript,
        function()
            return generatedLua
        end
    )

    return localScript
end

local function buildJob(job)
    local spec = job.scene_spec or {}
    local generatedLua = tostring(job.generated_lua or "")
    local packageName = "AIVideoGen_" .. tostring(job.job_id)

    local oldPackage = ReplicatedStorage:FindFirstChild(packageName)
    if oldPackage then
        oldPackage:Destroy()
    end

    local packageFolder = Instance.new("Folder")
    packageFolder.Name = packageName
    packageFolder.Parent = ReplicatedStorage

    local manifest = Instance.new("StringValue")
    manifest.Name = "SceneSpecJSON"
    manifest.Value = HttpService:JSONEncode(spec)
    manifest.Parent = packageFolder

    buildEnvironment(spec, packageFolder)
    buildGui(spec)
    local controller = importController(generatedLua)

    local marker = ServerScriptService:FindFirstChild(
        "AIVideoGenImportInfo"
    )
    if marker then
        marker:Destroy()
    end

    marker = Instance.new("Folder")
    marker.Name = "AIVideoGenImportInfo"
    marker:SetAttribute("JobId", tostring(job.job_id))
    marker:SetAttribute("SourceName", tostring(job.source_name))
    marker:SetAttribute("ImportedAtUnix", os.time())
    marker.Parent = ServerScriptService

    ChangeHistoryService:SetWaypoint(
        "AIVideoGen built " .. tostring(job.source_name)
    )
    Selection:Set({controller})

    return controller
end

local function fetchAndBuild()
    if busy then
        return
    end
    busy = true
    fetchGuiButton.Text = "Working..."

    local ok, err = pcall(function()
        setStatus("Contacting local AIVideoGen server...")

        local response = request({
            Url = BASE_URL .. "/api/roblox-plugin/next-job",
            Method = "GET",
        })

        local payload = HttpService:JSONDecode(response.Body)
        local job = payload.job

        if job == nil then
            setStatus("No pending job. Queue one in the web app first.")
            return
        end

        setStatus(
            "Building "
            .. tostring(job.source_name)
            .. "..."
        )

        buildJob(job)

        postStatus(
            tostring(job.job_id),
            "complete",
            "Scene, GUI, manifest and GeneratedScene imported."
        )

        setStatus(
            "Import complete.\n\n"
            .. "GeneratedScene is in StarterPlayerScripts.\n"
            .. "Environment is in Workspace/AIVideoGenGenerated.\n"
            .. "Press Play to test."
        )
    end)

    if not ok then
        setStatus("Error: " .. tostring(err))
    end

    busy = false
    fetchGuiButton.Text = "Fetch & Build"
end

fetchButton.Click:Connect(function()
    widget.Enabled = true
    fetchAndBuild()
end)

fetchGuiButton.MouseButton1Click:Connect(fetchAndBuild)

plugin.Unloading:Connect(function()
    print("[AIVideoGen] Plugin unloaded.")
end)
