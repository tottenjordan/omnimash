# 🎧 Multimodal Joint Latent Space Prompting & [AUDIO TRACK]

## 📌 Context & Discovery
In initial prototype tests, generated parody videos occasionally exhibited slight audio-video timing misalignment (e.g. character head bobs or speech gestures falling out of sync with the underlying beat). 

### Root Cause Analysis
- `gemini-omni-flash-preview` is a **native multimodal transformer**. It generates video frames and audio spectrograms simultaneously from a single joint latent space in one forward pass.
- When prompts only describe visual aesthetics and motion (e.g., *bopping head to a beat*) while relying on decoupled audio muxing, the model's visual attention heads are unaware of the acoustic beat onset times.
- By providing an explicit **`[AUDIO TRACK]`** descriptor co-located in the same structured prompt payload, Omni Flash's cross-attention layers bind the character's kinematic motion tokens directly to the acoustic spectrogram tempo.

---

## 🏗️ 6-Part Anchor & Inject Schema

Initial video turns are structured as a 6-part payload:

```text
[SUBJECT ANCHOR]: {character facial features, hair, likeness} | 
[AESTHETIC INJECTION]: {wardrobe, jewelry, street styling} | 
[ENVIRONMENT]: {background lighting, dungeon or stage setting} | 
[CAMERA/LIGHTING]: {lens choice, tracking shot, neon rim lights} | 
[MOTION]: {rhythmic gestures, head nodding} | 
[AUDIO TRACK]: {tempo BPM, 808 sub-bass, hi-hat trills, genre cadence}
```

### Multi-Turn Conversational Diff (Lock & Isolate)
```text
[PRESERVATION LOCK]: Maintain exact subject face, likeness, wardrobe, environment, and 120 BPM audio stem tempo from the previous turn. | 
[ISOLATED DIFF]: Alter only the specified visual or audio element.
```
