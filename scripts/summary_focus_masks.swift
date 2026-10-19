// Generate tracking mattes for the two live-action layers of the approved summary.
import Foundation
import Vision
import AVFoundation
import CoreImage
guard CommandLine.arguments.count == 3 else {
 fatalError("Usage: summary_focus_masks INPUT.mp4 WORK_DIRECTORY")
}
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
 let human=f<1644
 let hardware=f>=2820
 if !(human || hardware) || f%2 != 0 {continue}
 let destination=output.appendingPathComponent(String(format:"%04d.png",f))
 let extraDestination=extra.appendingPathComponent(String(format:"%04d.png",f))
 if FileManager.default.fileExists(atPath:destination.path) && (!human || FileManager.default.fileExists(atPath:extraDestination.path)){continue}
 try autoreleasepool {
  let buffer=CMSampleBufferGetImageBuffer(sample)!
  let im=CIImage(cvPixelBuffer:buffer)
  var x=hardware ? 976.0 : 24.0;var y=176.0;var w=920.0;var h=880.0
  if f<150 {
   let u=max(0.0,min(1.0,(Double(f)/60.0-1.1)/1.4));let v=u*u*(3-2*u)
   x=(24*v).rounded();y=(176*v).rounded();w=(1920-1000*v).rounded();h=(1080-200*v).rounded()
  }
  let crop=im.cropped(to:CGRect(x:x,y:1080-y-h,width:w,height:h)).transformed(by:CGAffineTransform(translationX:-x,y:-(1080-y-h)))
  let cg=ctx.createCGImage(crop,from:crop.extent)!
  let handler=VNImageRequestHandler(cgImage:cg)
  let result:CIImage
  if human {
   try handler.perform([person]);result=CIImage(cvPixelBuffer:person.results!.first!.pixelBuffer)
   let foreground=VNGenerateForegroundInstanceMaskRequest();try handler.perform([foreground])
   guard let r=foreground.results?.first, !r.allInstances.isEmpty else {fatalError("No human foreground at \(f)")}
   let fg=CIImage(cvPixelBuffer:try r.generateScaledMaskForImage(forInstances:r.allInstances,from:handler))
   try ctx.writePNGRepresentation(of:fg,to:extraDestination,format:.L8,colorSpace:CGColorSpaceCreateDeviceGray())
  } else {
   let foreground=VNGenerateForegroundInstanceMaskRequest();try handler.perform([foreground])
   guard let r=foreground.results?.first, !r.allInstances.isEmpty else {fatalError("No robot mask at \(f)")}
   result=CIImage(cvPixelBuffer:try r.generateScaledMaskForImage(forInstances:r.allInstances,from:handler))
  }
  try ctx.writePNGRepresentation(of:result,to:destination,format:.L8,colorSpace:CGColorSpaceCreateDeviceGray())
 }
 count += 1
 if count%60==0{print("Tracking mask \(f)/3598");fflush(stdout)}
}
guard reader.status == .completed else{fatalError("\(String(describing:reader.error))")}
print("Done: \(count) mattes from \(f) frames")
