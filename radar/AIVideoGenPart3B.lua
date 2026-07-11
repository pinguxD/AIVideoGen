-- AIVideoGen Studio Installer — Part 3B
-- Installs a Part 3A generated package into the currently open Studio place.

local HttpService = game:GetService("HttpService")
local ScriptEditorService = game:GetService("ScriptEditorService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local StarterPlayer = game:GetService("StarterPlayer")
local ServerScriptService = game:GetService("ServerScriptService")
local Lighting = game:GetService("Lighting")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local Selection = game:GetService("Selection")

local BASE_URL = "http://127.0.0.1:5000"

local toolbar = plugin:CreateToolbar("AIVideoGen")
local installButton = toolbar:CreateButton(
    "FetchInstall",
    "Fetch the next Part 3A package and install it",
    "rbxassetid://4458901886",
    "Fetch & Install"
)

local widgetInfo = DockWidgetPluginGuiInfo.new(
    Enum.InitialDockState.Left,
    true,
    false,
    390,
    470,
    300,
    260
)

local widget = plugin:CreateDockWidgetPluginGui(
    "AIVideoGenPart3BWidget",
    widgetInfo
)
widget.Title = "AIVideoGen Part 3B"

local rootFrame = Instance.new("Frame")
rootFrame.BackgroundColor3 = Color3.fromRGB(25, 29, 38)
rootFrame.Size = UDim2.fromScale(1, 1)
rootFrame.Parent = widget

local title = Instance.new("TextLabel")
title.BackgroundTransparency = 1
title.Text = "Studio Package Installer"
title.TextColor3 = Color3.new(1, 1, 1)
title.Font = Enum.Font.GothamBold
title.TextSize = 18
title.Size = UDim2.new(1, -20, 0, 42)
title.Position = UDim2.fromOffset(10, 8)
title.Parent = rootFrame

local status = Instance.new("TextLabel")
status.BackgroundColor3 = Color3.fromRGB(15, 18, 25)
status.TextColor3 = Color3.fromRGB(220, 226, 236)
status.TextWrapped = true
status.TextXAlignment = Enum.TextXAlignment.Left
status.TextYAlignment = Enum.TextYAlignment.Top
status.Font = Enum.Font.Code
status.TextSize = 14
status.Text = "Queue a Part 3A package in the web app, then click Fetch & Install."
status.Size = UDim2.new(1, -20, 1, -120)
status.Position = UDim2.fromOffset(10, 54)
status.Parent = rootFrame

local installGuiButton = Instance.new("TextButton")
installGuiButton.BackgroundColor3 = Color3.fromRGB(55, 96, 150)
installGuiButton.TextColor3 = Color3.new(1, 1, 1)
installGuiButton.Font = Enum.Font.GothamBold
installGuiButton.TextSize = 15
installGuiButton.Text = "Fetch & Install"
installGuiButton.Size = UDim2.new(1, -20, 0, 42)
installGuiButton.Position = UDim2.new(0, 10, 1, -54)
installGuiButton.Parent = rootFrame

local busy = false

local function setStatus(message)
    status.Text = message
    print("[AIVideoGen Part 3B] " .. message)
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
            "HTTP "
            .. tostring(response.StatusCode)
            .. ": "
            .. tostring(response.Body)
        )
    end

    return response
end

local function postJobStatus(jobId, endpoint, message)
    request({
        Url = BASE_URL
            .. "/api/scene-builder-plugin/jobs/"
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

local function ensureFolder(parent, name)
    local existing = parent:FindFirstChild(name)
    if existing and existing:IsA("Folder") then
        return existing
    end
    if existing then
        existing:Destroy()
    end

    local folder = Instance.new("Folder")
    folder.Name = name
    folder.Parent = parent
    return folder
end

local function setScriptSource(scriptObject, source)
    ScriptEditorService:UpdateSourceAsync(
        scriptObject,
        function()
            return source
        end
    )
end

local function installModule(
    modulesRoot,
    mechanicsRoot,
    file
)
    local relativePath = tostring(file.relative_path)
    local name = relativePath:match("([^/]+)%.lua$")
        or relativePath:match("([^/]+)%.luau$")
        or "GeneratedModule"

    local parent = modulesRoot
    if file.kind == "mechanic_module" then
        parent = mechanicsRoot
    end

    local existing = parent:FindFirstChild(name)
    if existing then
        existing:Destroy()
    end

    local moduleScript = Instance.new("ModuleScript")
    moduleScript.Name = name
    moduleScript.Parent = parent
    setScriptSource(moduleScript, tostring(file.content or "return {}"))

    return moduleScript
end

local function installClientScript(file)
    local scriptsFolder = StarterPlayer
        :WaitForChild("StarterPlayerScripts")

    local existing = scriptsFolder:FindFirstChild("GeneratedScene")
    if existing then
        existing:Destroy()
    end

    local localScript = Instance.new("LocalScript")
    localScript.Name = "GeneratedScene"
    localScript.Parent = scriptsFolder
    setScriptSource(localScript, tostring(file.content or ""))

    return localScript
end

local function buildEnvironment(blueprint)
    local environment = blueprint.environment_graph or {}
    local sceneType = tostring(
        environment.scene_type or "simple_platform"
    )

    local old = workspace:FindFirstChild("AIVideoGenGenerated")
    if old then
        old:Destroy()
    end

    local generated = Instance.new("Folder")
    generated.Name = "AIVideoGenGenerated"
    generated.Parent = workspace

    local function createPart(name, size, position, color)
        local part = Instance.new("Part")
        part.Name = name
        part.Anchored = true
        part.Size = size
        part.Position = position
        part.Color = color or Color3.fromRGB(210, 210, 210)
        part.Material = Enum.Material.SmoothPlastic
        part.Parent = generated
        return part
    end

    if sceneType == "simple_obby" then
        for index = 1, 10 do
            createPart(
                "Platform" .. index,
                Vector3.new(8, 1, 8),
                Vector3.new(
                    (index - 1) * 10,
                    (index % 3) * 2,
                    0
                ),
                Color3.fromHSV(index / 10, 0.7, 1)
            )
        end
    elseif sceneType == "hospital" then
        createPart(
            "HospitalFloor",
            Vector3.new(60, 1, 50),
            Vector3.new(0, 0, 0),
            Color3.fromRGB(225, 230, 235)
        )
        createPart(
            "HospitalBackWall",
            Vector3.new(60, 18, 1),
            Vector3.new(0, 9, 25),
            Color3.fromRGB(185, 210, 225)
        )
    elseif sceneType == "horror_corridor" then
        createPart(
            "CorridorFloor",
            Vector3.new(18, 1, 80),
            Vector3.new(0, 0, 0),
            Color3.fromRGB(42, 42, 42)
        )
        createPart(
            "LeftWall",
            Vector3.new(1, 18, 80),
            Vector3.new(-9, 9, 0),
            Color3.fromRGB(30, 30, 30)
        )
        createPart(
            "RightWall",
            Vector3.new(1, 18, 80),
            Vector3.new(9, 9, 0),
            Color3.fromRGB(30, 30, 30)
        )
    else
        createPart(
            "Baseplate",
            Vector3.new(80, 1, 80),
            Vector3.new(0, 0, 0),
            Color3.fromRGB(210, 210, 210)
        )
    end

    local spawn = Instance.new("SpawnLocation")
    spawn.Name = "GeneratedSpawn"
    spawn.Size = Vector3.new(8, 1, 8)
    spawn.Position = Vector3.new(0, 1, 0)
    spawn.Anchored = true
    spawn.Parent = generated

    return generated
end

local function applyLighting(blueprint)
    local lightingName = tostring(
        blueprint.lighting or "bright_cartoon"
    )

    if lightingName == "dark_horror" then
        Lighting.Brightness = 1
        Lighting.ClockTime = 1
        Lighting.Ambient = Color3.fromRGB(25, 25, 35)
        Lighting.OutdoorAmbient = Color3.fromRGB(15, 15, 20)
    elseif lightingName == "clean_indoor" then
        Lighting.Brightness = 2.5
        Lighting.ClockTime = 13
        Lighting.Ambient = Color3.fromRGB(170, 180, 195)
    else
        Lighting.Brightness = 3
        Lighting.ClockTime = 14
        Lighting.Ambient = Color3.fromRGB(150, 160, 180)
        Lighting.OutdoorAmbient = Color3.fromRGB(130, 140, 160)
    end
end

local function installPackage(job)
    local blueprint = job.blueprint or {}
    local files = job.files or {}

    local oldPackage = ReplicatedStorage:FindFirstChild(
        "AIVideoGenPackage"
    )
    if oldPackage then
        oldPackage:Destroy()
    end

    local packageRoot = Instance.new("Folder")
    packageRoot.Name = "AIVideoGenPackage"
    packageRoot:SetAttribute("BuildId", tostring(job.build_id))
    packageRoot:SetAttribute(
        "SourceName",
        tostring(job.source_name)
    )
    packageRoot.Parent = ReplicatedStorage

    local modulesRoot = ensureFolder(packageRoot, "Modules")
    local mechanicsRoot = ensureFolder(
        modulesRoot,
        "Mechanics"
    )

    local manifest = Instance.new("StringValue")
    manifest.Name = "BlueprintJSON"
    manifest.Value = HttpService:JSONEncode(blueprint)
    manifest.Parent = packageRoot

    local installed = {}
    local selected = {}

    for _, file in ipairs(files) do
        if (
            file.kind == "module"
            or file.kind == "mechanic_module"
        ) then
            local object = installModule(
                modulesRoot,
                mechanicsRoot,
                file
            )
            table.insert(installed, object:GetFullName())
            table.insert(selected, object)
        elseif file.kind == "client_script" then
            local object = installClientScript(file)
            table.insert(installed, object:GetFullName())
            table.insert(selected, object)
        end
    end

    local generated = buildEnvironment(blueprint)
    applyLighting(blueprint)

    local marker = ServerScriptService:FindFirstChild(
        "AIVideoGenBuildInfo"
    )
    if marker then
        marker:Destroy()
    end

    marker = Instance.new("Folder")
    marker.Name = "AIVideoGenBuildInfo"
    marker:SetAttribute("JobId", tostring(job.job_id))
    marker:SetAttribute("BuildId", tostring(job.build_id))
    marker:SetAttribute(
        "SourceName",
        tostring(job.source_name)
    )
    marker:SetAttribute("InstalledAtUnix", os.time())
    marker.Parent = ServerScriptService

    ChangeHistoryService:SetWaypoint(
        "AIVideoGen installed " .. tostring(job.build_id)
    )

    table.insert(selected, generated)
    Selection:Set(selected)

    return installed
end

local function fetchAndInstall()
    if busy then
        return
    end

    busy = true
    installGuiButton.Text = "Installing..."

    local jobId = nil
    local ok, result = pcall(function()
        setStatus("Fetching the next Studio package...")

        local response = request({
            Url = BASE_URL
                .. "/api/scene-builder-plugin/next-job",
            Method = "GET",
        })
        local payload = HttpService:JSONDecode(response.Body)

        if not payload.ok then
            error(payload.error or "Server returned an error.")
        end

        local job = payload.job
        if job == nil then
            setStatus(
                "No pending Part 3B job.\n\n"
                .. "Queue a package in the web app first."
            )
            return
        end

        jobId = tostring(job.job_id)

        setStatus(
            "Installing build "
            .. tostring(job.build_id)
            .. "...\n\n"
            .. "Files received: "
            .. tostring(#(job.files or {}))
        )

        local installed = installPackage(job)

        postJobStatus(
            jobId,
            "complete",
            "Installed "
            .. tostring(#installed)
            .. " scripts/modules and built the environment."
        )

        setStatus(
            "Installation complete.\n\n"
            .. "Workspace/AIVideoGenGenerated created.\n"
            .. "ReplicatedStorage/AIVideoGenPackage created.\n"
            .. "StarterPlayerScripts/GeneratedScene created.\n\n"
            .. "Press Play to test the generated scene."
        )
    end)

    if not ok then
        local message = tostring(result)
        setStatus("Installation failed:\n\n" .. message)

        if jobId then
            pcall(function()
                postJobStatus(jobId, "fail", message)
            end)
        end
    end

    busy = false
    installGuiButton.Text = "Fetch & Install"
end

installButton.Click:Connect(function()
    widget.Enabled = true
    fetchAndInstall()
end)

installGuiButton.MouseButton1Click:Connect(fetchAndInstall)
