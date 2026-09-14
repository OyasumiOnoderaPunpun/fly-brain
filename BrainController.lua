-- Place this Script inside the Fruit Fly NPC model (or ServerScriptService if it handles all flies)
-- Make sure to enable "Allow HTTP Requests" in Game Settings > Security

local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")

-- The URL to our local Python server running the PyTorch Fly Brain
local FLY_BRAIN_URL = "http://127.0.0.1:5000/talk"

local FlyNPC = script.Parent
local Head

if FlyNPC:IsA("Model") then
	Head = FlyNPC:FindFirstChild("Head") or FlyNPC:FindFirstChild("HumanoidRootPart")
elseif FlyNPC:IsA("BasePart") then
	Head = FlyNPC
end

-- If the user didn't put the script inside a model or part, let's just create a Fly for them!
if not Head or not Head:IsA("BasePart") then
	warn("Script wasn't placed inside a model with a Head or a Part. Generating a Fly automatically...")
	Head = Instance.new("Part")
	Head.Name = "Head"
	Head.Size = Vector3.new(1, 1, 1)
	Head.Position = Vector3.new(0, 5, -10)
	Head.Color = Color3.new(0.2, 0.2, 0.2)
	Head.Transparency = 1 -- Make the solid block invisible
	Head.Anchored = true
	Head.Parent = workspace
	
	-- Create a BillboardGui so the fly always faces the camera like a 2D sprite
	local billboard = Instance.new("BillboardGui")
	billboard.Size = UDim2.new(4, 0, 4, 0) -- 4x4 studs
	billboard.AlwaysOnTop = false -- Now respects 3D depth!
	billboard.Parent = Head
	
	local imageLabel = Instance.new("ImageLabel")
	imageLabel.Size = UDim2.new(1, 0, 1, 0)
	imageLabel.BackgroundTransparency = 1 -- Transparent background!
	imageLabel.Image = "rbxthumb://type=Asset&id=1566392136&w=420&h=420"
	imageLabel.Parent = billboard
end

-- Function to ping the Python Brain
local function getFlyBrainResponse(message, playerName)
	local payload = {
		["message"] = message,
		["player"] = playerName
	}
	
	local success, response = pcall(function()
		return HttpService:PostAsync(FLY_BRAIN_URL, HttpService:JSONEncode(payload), Enum.HttpContentType.ApplicationJson)
	end)
	
	if success then
		local decoded = HttpService:JSONDecode(response)
		return decoded.response, decoded.active_neurons
	else
		warn("Failed to connect to Fly Brain Server: " .. tostring(response))
		return "*The fly ignores you (server offline)*", {}
	end
end

-- Hologram visualization folder
local HologramFolder = workspace:FindFirstChild("FlyHologram")
if not HologramFolder then
	HologramFolder = Instance.new("Folder")
	HologramFolder.Name = "FlyHologram"
	HologramFolder.Parent = workspace
end

local function renderBrainHologram(active_neurons, headPart)
	HologramFolder:ClearAllChildren()
	if not active_neurons then return end
	
	-- Calculate base position (5 studs above and to the right)
	local center = headPart.Position + Vector3.new(5, 5, 0)
	
	for i, neuron_id in ipairs(active_neurons) do
		-- Map 130,000 ID to a random position in a 4x4x4 cube
		local rng = Random.new(neuron_id)
		local offset = Vector3.new(rng:NextNumber(-2, 2), rng:NextNumber(-2, 2), rng:NextNumber(-2, 2))
		
		local part = Instance.new("Part")
		part.Size = Vector3.new(0.2, 0.2, 0.2)
		part.Position = center + offset
		part.Anchored = true
		part.CanCollide = false
		part.Material = Enum.Material.Neon
		part.Color = Color3.fromHSV(i / #active_neurons, 1, 1) -- Rainbow colors
		part.Parent = HologramFolder
		
		-- Create a connection to the center
		local att0 = Instance.new("Attachment", part)
		local att1 = Instance.new("Attachment", headPart)
		local beam = Instance.new("Beam")
		beam.Attachment0 = att0
		beam.Attachment1 = att1
		beam.FaceCamera = true
		beam.Width0 = 0.05
		beam.Width1 = 0.01
		beam.Color = ColorSequence.new(part.Color)
		beam.Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 0.5),
			NumberSequenceKeypoint.new(1, 1)
		})
		beam.Parent = part
	end
end

-- Listen to chat messages using Player.Chatted (works on Server scripts)
local function onPlayerAdded(player)
	player.Chatted:Connect(function(message)
		local character = player.Character
		if character and character:FindFirstChild("HumanoidRootPart") and Head then
			local distance = (character.HumanoidRootPart.Position - Head.Position).Magnitude
			if distance < 15 then -- Player is within 15 studs
				print(player.Name .. " said something near the fly. Processing in biological brain...")
				
				-- Show a 'thinking' indicator over the fly's head so players know it's processing
				pcall(function()
					game:GetService("Chat"):Chat(Head, "*Thinking... (~5 seconds)*", Enum.ChatColor.White)
				end)
				
				-- Send message to the Python connectome and get the action
				local brainAction, active_neurons = getFlyBrainResponse(message, player.Name)
				print("Brain Action received: " .. tostring(brainAction))
				
				-- Render the active neurons in the physical world!
				renderBrainHologram(active_neurons, Head)
				
				-- Use modern TextChatService to display the bubble over the part
				local TextChatService = game:GetService("TextChatService")
				pcall(function()
					TextChatService:DisplayBubble(Head, brainAction)
				end)
				
				-- Fallback to Legacy Chat just in case BubbleChat is disabled
				pcall(function()
					game:GetService("Chat"):Chat(Head, brainAction, Enum.ChatColor.White)
				end)
			end
		end
	end)
end

Players.PlayerAdded:Connect(onPlayerAdded)
-- CRITICAL FIX: In Roblox Studio, the local player often loads BEFORE the script starts.
-- We must loop through existing players to attach the chat event to them!
for _, player in ipairs(Players:GetPlayers()) do
	onPlayerAdded(player)
end
