"""_summary_
write a script that takes a video file and a list of audio files and stitches them together.
The audio files are named with the time they should be inserted into the video.
For each audio file, pause the video, seek to the correct time, play the audio, then resume the video.
Each audio file also has a corresponding cursor trajectory file, which displays a cursor on the video.
Draw the cursor on the video as the audio plays. The cursor trajectory file is a list of (x, y) coordinates
save in a json file with the same name as the audio file.
"""

import json
import argparse
import os
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, VideoClip, CompositeVideoClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.video.fx.all import freeze
from PIL import Image, ImageDraw
import numpy as np

class CursorClip(VideoClip):
    def __init__(self, frame, trajectory, duration, width, height):
        self.trajectory = trajectory
        self.cursor_duration = duration / len(trajectory)
        self.frame = Image.fromarray(frame)

        def make_frame(t):
            i = int(t / self.cursor_duration)
            # frame = Image.new('RGB', (width, height), (0, 0, 0))  # Assuming width and height are defined elsewhere

            if i < len(self.trajectory):
                x, y = self.trajectory[i]
                draw = ImageDraw.Draw(self.frame)
                draw.ellipse((x-5, y-5, x+5, y+5), fill='red')

            return np.array(self.frame)  # Convert the PIL image to a NumPy array

        super().__init__(make_frame, duration=duration)

def stitch_video_audio(video_file, audio_dir, output_file):
    # Get all audio files
    audio_files = sorted([os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.endswith('.wav')])
    # get all json files
    json_files = sorted([os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.endswith('.json')])
    
    # assert their file names match
    assert set([os.path.splitext(os.path.basename(f))[0] for f in audio_files]) == set([os.path.splitext(os.path.basename(f))[0] for f in json_files])
                                                                                       
    # Load video file
    video = VideoFileClip(video_file)
    final_clips = []
    
    insertion_times = []
    insertion_clips = []

    for audio_file, json_file in zip(audio_files, json_files):
        # Extract the time from the audio file name
        time_str = os.path.splitext(os.path.basename(audio_file))[0]
        insertion_time = int(time_str) / 1000.0

        # Split video at insertion_time
        if insertion_time < video.duration:
            clip1 = video.subclip(0, insertion_time)
            clip2 = video.subclip(insertion_time, video.duration)
        else:
            clip1 = video
            clip2 = None

        # Load audio file
        audio = AudioFileClip(audio_file)

        # Pause the video at insertion_time and play the audio
        freeze_time = audio.duration
        frozen_frame = freeze(clip1, t=insertion_time, freeze_duration=freeze_time).subclip(clip1.duration, clip1.duration + freeze_time)

        # Apply the cursor trajectory
        with open(json_file, 'r') as f:
            trajectory = json.load(f)
        
        # Create the cursor clip
        # get the first frame of the frozen video as numpy
        frame = video.get_frame(insertion_time).astype(np.uint8)
        cursor_clip = CursorClip(frame, trajectory, audio.duration, width=video.size[0], height=video.size[1])
        insertion_clips.append(cursor_clip.set_audio(audio))
        insertion_times.append(insertion_time)
    
    # insert all clips into the video at the correct time
    # first modify insertion_times to be relative to the previous insertion time
    relative_insertion_times = [0] + [insertion_times[i] - insertion_times[i-1] for i in range(1, len(insertion_times))]
    for relative_insert_time, insertion_clip in zip(relative_insertion_times, insertion_clips):
        clip1 = video.subclip(0, relative_insert_time)
        clip2 = video.subclip(relative_insert_time, video.duration)
        final_clips.append(clip1)
        final_clips.append(insertion_clip)
        video = clip2
    final_clips.append(clip2)

    # Concatenate all clips and write the output file
    final_video = concatenate_videoclips(final_clips)
    final_video.write_videofile(output_file)
    

if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser(description='Stitch video and audio files together.')
    parser.add_argument('--video-file', type=str, help='Path to the video file.')
    parser.add_argument('--narration-dir', type=str, help='Path to the directory containing the audio files and cursor trajectory files.')
    parser.add_argument('--output-file', type=str, help='Path to the output file.')
    args = parser.parse_args()
    
    stitch_video_audio(args.video_file, args.narration_dir, args.output_file)
    
    # python3 stitch_videos.py --video-file /Users/changan/Downloads/0.mp4 --narration-dir epic_narrator_recordings/0 --output-file final_output.mp4