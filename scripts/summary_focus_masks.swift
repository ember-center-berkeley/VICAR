// Generate human tracking mattes for the summary or the ladder hero.
import Foundation
import Vision
import AVFoundation
import CoreImage
guard CommandLine.arguments.count == 3 || (CommandLine.arguments.count == 4 && CommandLine.arguments[3] == "ladder") else {
 fatalError("Usage: summary_focus_masks INPUT.mp4 WORK_DIRECTORY [ladder]")
}
let ladder = CommandLine.arguments.count == 4
let work = URL(fileURLWithPath:CommandLine.arguments[2],isDirectory:true)
let output = work.appendingPathComponent("masks",isDirectory:true)
let extra = work.appendingPathComponent("foreground",isDirectory:true)
for dir in [output,extra] {try FileManager.default.createDirectory(at:dir,withIntermediateDirectories:true)}
let source = URL(fileURLWithPath:CommandLine.arguments[1])
let asset = AVURLAsset(url:source)
let track = try await asset.loadTracks(withMediaType:.video).first!
let reader = try AVAssetReader(asset:asset)
let stream = AVAssetReaderTrackOutput(track:track,outputSettings:[kCVPixelBufferPixelFormatTypeKey as String:kCVPixelFormatType_32BGRA])
reader.add(stream);reader.startReading()
let ctx=CIContext(options:[.cacheIntermediates:false])
let person=VNGeneratePersonSegmentationRequest();person.qualityLevel = .accurate;person.outputPixelFormat = kCVPixelFormatType_OneComponent8
var f=0;var count=0
while let sample=stream.copyNextSampleBuffer() {
 defer { f += 1 }
 let human=ladder || f<1644
 if !human || f%2 != 0 {continue}
 if ladder && (f<10 || f>594) {continue}
 let destination=output.appendingPathComponent(String(format:"%04d.png",f))
 let extraDestination=extra.appendingPathComponent(String(format:"%04d.png",f))
 if FileManager.default.fileExists(atPath:destination.path) && FileManager.default.fileExists(atPath:extraDestination.path){continue}
 try autoreleasepool {
  let buffer=CMSampleBufferGetImageBuffer(sample)!
  let im=CIImage(cvPixelBuffer:buffer)
  var x=24.0;var y=176.0;var w=920.0;var h=880.0
  if !ladder && f<150 {
   let u=max(0.0,min(1.0,(Double(f)/60.0-1.1)/1.4));let v=u*u*(3-2*u)
   x=(24*v).rounded();y=(176*v).rounded();w=(1920-1000*v).rounded();h=(1080-200*v).rounded()
  }
  let frameHeight=Double(CVPixelBufferGetHeight(buffer))
  if ladder {x=0;y=0;w=Double(CVPixelBufferGetWidth(buffer));h=frameHeight}
  let crop=im.cropped(to:CGRect(x:x,y:frameHeight-y-h,width:w,height:h)).transformed(by:CGAffineTransform(translationX:-x,y:-(frameHeight-y-h)))
  let cg=ctx.createCGImage(crop,from:crop.extent)!
  let handler=VNImageRequestHandler(cgImage:cg)
  let result:CIImage
  try handler.perform([person]);result=CIImage(cvPixelBuffer:person.results!.first!.pixelBuffer)
  let foreground=VNGenerateForegroundInstanceMaskRequest();try handler.perform([foreground])
  guard let r=foreground.results?.first, !r.allInstances.isEmpty else {fatalError("No human foreground at \(f)")}
  let fg=CIImage(cvPixelBuffer:try r.generateScaledMaskForImage(forInstances:r.allInstances,from:handler))
  try ctx.writePNGRepresentation(of:fg,to:extraDestination,format:.L8,colorSpace:CGColorSpaceCreateDeviceGray())
  try ctx.writePNGRepresentation(of:result,to:destination,format:.L8,colorSpace:CGColorSpaceCreateDeviceGray())
 }
 count += 1
 if count%60==0{print("Tracking mask \(f)/\(ladder ? 605 : 3598)");fflush(stdout)}
}
guard reader.status == .completed else{fatalError("\(String(describing:reader.error))")}
print("Done: \(count) mattes from \(f) frames")
