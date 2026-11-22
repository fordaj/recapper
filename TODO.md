## Important Design Direction: Timeline-First Editor

Use a traditional video-editing timeline as the primary editing interface, rather than a storyboard or vertical clip list.

However, Recapper should feel considerably simpler and more approachable than professional editing software like Premiere Pro or DaVinci Resolve.

### Layout

Explore a layout with:

- **Preview:** A prominent video preview showing the assembled project or selected clip.
- **Media Library:** Imported photos, videos, and audio available for use.
- **Properties Inspector:** Context-sensitive controls for the currently selected clip or track.
- **Timeline:** The primary workspace, occupying the bottom portion of the editor.

### Timeline

The timeline should support the conceptual editing model:

- Horizontal time progression.
- Video clips represented by thumbnail strips.
- Images represented by thumbnail clips with configurable durations.
- Title slides represented by distinctive visual clips.
- Side-by-side compositions represented as a single composition clip.
- Audio tracks displayed separately with waveform-style visualizations.
- Multiple tracks where appropriate.
- Drag-and-drop clip reordering.
- Playhead and time ruler.
- Clip selection, trimming, and duration adjustment.
- Clear visual distinction between media types.

### Editing Experience

Prioritize usability over professional editing complexity.

- Selecting a clip should update the properties inspector.
- Users should be able to adjust duration, title text, composition, and other relevant properties.
- Clips should have intuitive drag handles and selection states.
- The playhead should communicate the current preview position.
- Audio should be visually distinguishable from video.
- Timeline zoom should be considered if it materially improves usability.

Do not introduce unnecessary professional editing features such as complex keyframe editors, advanced color grading, or dozens of track types.

### Design Philosophy

Think of a simplified desktop video editor designed specifically for creating family recaps.

The timeline is the central organizing tool, while the media library, preview, and properties inspector support it.

The result should feel like a real editing application, not a dashboard with a video player attached.
