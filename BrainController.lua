-- Place this Script inside the Fruit Fly NPC model (or ServerScriptService if it handles all flies)
-- Make sure to enable "Allow HTTP Requests" in Game Settings > Security

local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local TextService = game:GetService("TextService")
local RunService = game:GetService("RunService")

-- The URL to our live Python server running the PyTorch Fly Brain
local FLY_BRAIN_URL = "https://fly-brain.onrender.com/talk"
local TICK_URL = "https://fly-brain.onrender.com/tick"

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
				
				-- Filter the AI response through Roblox's Text Filter
				local filteredAction = brainAction
				local successFilter, filterResult = pcall(function()
					local textFilterResult = TextService:FilterStringAsync(brainAction, player.UserId)
					return textFilterResult:GetNonChatStringForBroadcastAsync()
				end)
				
				if successFilter and filterResult then
					filteredAction = filterResult
				else
					-- Fallback to hashes if filtering fails
					filteredAction = string.rep("#", math.min(string.len(brainAction), 50))
				end
				
				-- Render the active neurons in the physical world!
				renderBrainHologram(active_neurons, Head)
				
				-- Use modern TextChatService to display the bubble over the part
				local TextChatService = game:GetService("TextChatService")
				pcall(function()
					TextChatService:DisplayBubble(Head, filteredAction)
				end)
				
				-- Fallback to Legacy Chat just in case BubbleChat is disabled
				pcall(function()
					game:GetService("Chat"):Chat(Head, filteredAction, Enum.ChatColor.White)
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

-- PHYSICAL BODY SIMULATION
local currentMoveForward = 0
local currentMoveUp = 0
local currentMoveDown = 0
local currentYaw = 0
local currentPitch = 0
local currentRoll = 0

local function getFlyBrainTick(vision_fwd, vision_left, vision_right, vision_up, vision_down, player_dist)
	local payload = {
		["vision_fwd"] = vision_fwd,
		["vision_left"] = vision_left,
		["vision_right"] = vision_right,
		["vision_up"] = vision_up,
		["vision_down"] = vision_down,
		["player_dist"] = player_dist
	}
	
	local success, response = pcall(function()
		return HttpService:PostAsync(TICK_URL, HttpService:JSONEncode(payload), Enum.HttpContentType.ApplicationJson)
	end)
	
	if success then
		local decoded = HttpService:JSONDecode(response)
		return decoded.motor, decoded.active_neurons
	end
	return nil, nil
end

task.spawn(function()
	while task.wait(0.2) do -- 5 ticks a second for sensory processing
		if not Head then continue end
		
		-- Raycast forward (Sensory Vision)
		local fwdRay = workspace:Raycast(Head.Position, Head.CFrame.LookVector * 10)
		local vision_fwd = fwdRay and (fwdRay.Position - Head.Position).Magnitude / 10 or 1.0
		
		-- Raycast left
		local leftRay = workspace:Raycast(Head.Position, -Head.CFrame.RightVector * 10)
		local vision_left = leftRay and (leftRay.Position - Head.Position).Magnitude / 10 or 1.0
		
		-- Raycast right
		local rightRay = workspace:Raycast(Head.Position, Head.CFrame.RightVector * 10)
		local vision_right = rightRay and (rightRay.Position - Head.Position).Magnitude / 10 or 1.0
		
		-- Raycast up
		local upRay = workspace:Raycast(Head.Position, Head.CFrame.UpVector * 10)
		local vision_up = upRay and (upRay.Position - Head.Position).Magnitude / 10 or 1.0
		
		-- Raycast down
		local downRay = workspace:Raycast(Head.Position, -Head.CFrame.UpVector * 10)
		local vision_down = downRay and (downRay.Position - Head.Position).Magnitude / 10 or 1.0
		
		-- Nearest player dist (Sensory Proximity)
		local nearestDist = 100
		for _, player in ipairs(Players:GetPlayers()) do
			if player.Character and player.Character:FindFirstChild("HumanoidRootPart") then
				local dist = (player.Character.HumanoidRootPart.Position - Head.Position).Magnitude
				if dist < nearestDist then
					nearestDist = dist
				end
			end
		end
		local player_dist = nearestDist / 100 -- normalize 0-1
		
		-- Send senses to the biological connectome
		local motor, active_neurons = getFlyBrainTick(vision_fwd, vision_left, vision_right, vision_up, vision_down, player_dist)
		if motor then
			currentMoveForward = motor.move_forward
			currentMoveUp = motor.move_up
			currentMoveDown = motor.move_down
			currentYaw = motor.yaw
			currentPitch = motor.pitch
			currentRoll = motor.roll
			
			-- Render hologram of the active neural pathways
			pcall(function() renderBrainHologram(active_neurons, Head) end)
		end
	end
end)

RunService.Heartbeat:Connect(function(dt)
	if not Head or not Head.Anchored then return end
	
	-- The neural network outputs very small raw firing rates initially
	-- We amplify these significantly to map them to Roblox physics.
	-- We treat the single outputs as bidirectional if we subtract them, but for pitch/yaw/roll we just use the raw value since it can swing both ways via noise,
	-- Wait, ReLU only outputs positive numbers! So we must offset them, or the neural net will only turn right and pitch up.
	-- Let's offset the raw ReLU by its mean or just subtract a baseline (e.g. 0.05 * multiplier) so it can go negative.
	local yawSpeed = (currentYaw - 0.05) * 5000
	local pitchSpeed = (currentPitch - 0.05) * 5000
	local rollSpeed = (currentRoll - 0.05) * 5000
	
	local moveZ = (currentMoveForward - 0.05) * 10000 -- Forward/Back
	local moveY = (currentMoveUp - currentMoveDown) * 10000 -- Up/Down
	
	-- Cap maximum biological limits
	yawSpeed = math.clamp(yawSpeed, -15, 15)
	pitchSpeed = math.clamp(pitchSpeed, -15, 15)
	rollSpeed = math.clamp(rollSpeed, -15, 15)
	moveZ = math.clamp(moveZ, -10, 25)
	moveY = math.clamp(moveY, -15, 15)
	
	-- Apply movement (6DOF CFrame)
	-- Angles in X (pitch), Y (yaw), Z (roll)
	Head.CFrame = Head.CFrame * CFrame.Angles(math.rad(pitchSpeed * 60 * dt), math.rad(-yawSpeed * 60 * dt), math.rad(rollSpeed * 60 * dt))
	Head.CFrame = Head.CFrame * CFrame.new(0, moveY * dt, -moveZ * dt)
	
	-- Optional: If the fly hits the ground, don't let it clip through
	if Head.Position.Y < 1 then
		Head.CFrame = Head.CFrame - Vector3.new(0, Head.Position.Y - 1, 0)
	end
end)
